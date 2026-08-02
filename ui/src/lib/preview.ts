/**
 * Live attrition preview client.
 *
 * Type-ahead means concurrent requests, and responses land out of order. A stale
 * response overwriting a fresh one puts the wrong attrition number next to the
 * rule on screen — in this tool that is a credibility wound, not a glitch, so
 * staleness is handled explicitly rather than hoped away:
 *
 *   - debounce keystrokes (~150ms)
 *   - tag every request with a monotonic sequence number
 *   - DISCARD any response older than the newest already applied
 *   - abort in-flight requests when a newer keystroke arrives
 *
 * The last two are separate defences on purpose. Aborting is best-effort — a
 * response can already be in flight past the point of cancellation — so the
 * sequence check is the one that actually guarantees correctness.
 */

export interface Diagnostic {
  index: number;
  text: string;
  kind: string;
  ok: boolean;
  message: string;
  column: number | null;
}

export interface CriterionImpact {
  criterion: string;
  kind: string;
  screened_out: number;
  screened_out_rate: number;
  sole_reason: number;
}

export interface RuleAttribution {
  criterion: string;
  kind: string;
  shapley: number;
  shapley_share: number;
  screened_out: number;
  sole_reason: number;
}

export interface PreviewResult {
  sequence: number;
  cohort: { identity: string; size: number; cached: boolean };
  diagnostics: Diagnostic[];
  stale: boolean;
  stale_reason: string;
  eligible: number;
  screened: number;
  eligibility_rate: number;
  criteria_impact: CriterionImpact[];
  attribution: RuleAttribution[];
}

export interface PreviewRequest {
  condition: string;
  n: number;
  seed: number;
  inclusion: string[];
  exclusion: string[];
}

export const DEBOUNCE_MS = 150;

/** Ordered, cancellable preview requests. One instance per editor. */
export class PreviewChannel {
  private sequence = 0;
  private applied = -1;
  private inflight: AbortController | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly send: (
      body: PreviewRequest & { sequence: number },
      signal: AbortSignal,
    ) => Promise<PreviewResult>,
    private readonly debounceMs: number = DEBOUNCE_MS,
  ) {}

  /** Number of responses discarded for arriving out of order. Observable so a
   *  test can prove the guard fires rather than assuming it. */
  discarded = 0;

  request(body: PreviewRequest, onResult: (result: PreviewResult) => void): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.fire(body, onResult), this.debounceMs);
  }

  /** Bypasses the debounce — for the first paint and for explicit actions. */
  async fire(
    body: PreviewRequest,
    onResult: (result: PreviewResult) => void,
  ): Promise<void> {
    this.inflight?.abort();
    const controller = new AbortController();
    this.inflight = controller;

    const sequence = ++this.sequence;
    let result: PreviewResult;
    try {
      result = await this.send({ ...body, sequence }, controller.signal);
    } catch (error) {
      // An abort is the expected outcome of typing another character, not a
      // failure worth surfacing.
      if ((error as Error)?.name === "AbortError") return;
      throw error;
    }

    // The guarantee. Aborting is best-effort; this is not.
    if (result.sequence <= this.applied) {
      this.discarded += 1;
      return;
    }
    this.applied = result.sequence;
    onResult(result);
  }

  cancel(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.inflight?.abort();
  }
}

export async function postPreview(
  body: PreviewRequest & { sequence: number },
  signal: AbortSignal,
): Promise<PreviewResult> {
  const response = await fetch("/scenario/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw new Error(`preview failed: ${response.status}`);
  return (await response.json()) as PreviewResult;
}
