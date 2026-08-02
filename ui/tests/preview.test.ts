import { describe, expect, it, vi } from "vitest";
import { PreviewChannel, type PreviewRequest, type PreviewResult } from "../src/lib/preview";

const base: PreviewRequest = {
  condition: "type 2 diabetes", n: 100, seed: 42, inclusion: [], exclusion: [],
};

function reply(sequence: number, eligible: number): PreviewResult {
  return {
    sequence, eligible, screened: 100, eligibility_rate: eligible / 100,
    cohort: { identity: "t2d@v1", size: 100, cached: true },
    diagnostics: [], stale: false, stale_reason: "",
    criteria_impact: [], attribution: [],
  };
}

describe("out-of-order responses", () => {
  it("discards a stale response instead of overwriting a fresher one", async () => {
    // The failure this prevents: response 1 lands after response 2 and puts the
    // wrong attrition next to the rule on screen.
    // Resolvers, stored by sequence so the test can land them out of order.
    const pending: (() => void)[] = [];
    const channel = new PreviewChannel(
      (body) => new Promise((resolve) => { pending[body.sequence] = () => resolve(reply(body.sequence, body.sequence * 10)); }),
      0,
    );

    const applied: number[] = [];
    const first = channel.fire(base, (r) => applied.push(r.eligible));
    const second = channel.fire(base, (r) => applied.push(r.eligible));

    pending[2]!();          // newer lands first
    await second;
    pending[1]!();          // older lands late
    await first;

    expect(applied).toEqual([20]);
    expect(channel.discarded).toBe(1);
  });

  it("applies responses that arrive in order", async () => {
    const channel = new PreviewChannel(async (body) => reply(body.sequence, body.sequence), 0);
    const applied: number[] = [];
    await channel.fire(base, (r) => applied.push(r.sequence));
    await channel.fire(base, (r) => applied.push(r.sequence));
    expect(applied).toEqual([1, 2]);
    expect(channel.discarded).toBe(0);
  });

  it("aborts the in-flight request when a newer one starts", async () => {
    const signals: AbortSignal[] = [];
    const channel = new PreviewChannel(async (body, signal) => {
      signals.push(signal);
      return reply(body.sequence, 1);
    }, 0);

    await channel.fire(base, () => undefined);
    await channel.fire(base, () => undefined);
    expect(signals[0]!.aborted).toBe(true);
    expect(signals[1]!.aborted).toBe(false);
  });

  it("swallows abort errors rather than surfacing them", async () => {
    const channel = new PreviewChannel(async () => {
      const error = new Error("aborted");
      error.name = "AbortError";
      throw error;
    }, 0);
    await expect(channel.fire(base, () => undefined)).resolves.toBeUndefined();
  });

  it("debounces keystrokes into a single request", async () => {
    vi.useFakeTimers();
    const send = vi.fn(async (body: PreviewRequest & { sequence: number }) => reply(body.sequence, 1));
    const channel = new PreviewChannel(send, 150);

    channel.request(base, () => undefined);
    channel.request(base, () => undefined);
    channel.request(base, () => undefined);
    await vi.advanceTimersByTimeAsync(200);

    expect(send).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});
