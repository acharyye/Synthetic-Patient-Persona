import { describe, expect, it } from "vitest";
import { decodeState, encodeState, DEFAULT_STATE, type LabState } from "../src/lib/urlState";

describe("reproducibility in the URL", () => {
  it("round-trips every input that determines the simulation", () => {
    const state: LabState = {
      condition: "COPD", seed: 1234, n: 250,
      inclusion: ["age >= 50", "stage >= GOLD2"],
      exclusion: ["lung cancer"],
    };
    expect(decodeState(encodeState(state))).toEqual(state);
  });

  it("a shared link reproduces the same cohort identity inputs", () => {
    const shared = encodeState({ ...DEFAULT_STATE, seed: 7, n: 300 });
    const received = decodeState(shared);
    expect(received.seed).toBe(7);
    expect(received.n).toBe(300);
  });

  it("falls back cleanly on a malformed link", () => {
    const state = decodeState("?seed=banana&n=");
    expect(state.seed).toBe(DEFAULT_STATE.seed);
    expect(state.n).toBe(DEFAULT_STATE.n);
  });

  it("drops blank rules so the URL stays readable", () => {
    const encoded = encodeState({ ...DEFAULT_STATE, inclusion: ["age >= 50", "", "  "] });
    expect(encoded.match(/inc=/g)).toHaveLength(1);
  });
});

describe("blank and hostile params", () => {
  it("treats a blank value as absent, not as zero", () => {
    // Number("") === 0, which is finite — without a guard this would send a
    // cohort size of 0 to the server.
    expect(decodeState("?n=").n).toBe(DEFAULT_STATE.n);
    expect(decodeState("?n=%20%20").n).toBe(DEFAULT_STATE.n);
  });

  it("rejects a non-positive cohort size", () => {
    expect(decodeState("?n=0").n).toBe(DEFAULT_STATE.n);
    expect(decodeState("?n=-5").n).toBe(DEFAULT_STATE.n);
  });

  it("keeps a legitimate zero seed", () => {
    expect(decodeState("?seed=0").seed).toBe(0);
  });
});
