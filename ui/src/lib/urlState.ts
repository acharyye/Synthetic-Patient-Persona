/**
 * Reproducibility state lives in the URL.
 *
 * Pack, seed, size and the rule set are encoded in the route, so any Scenario Lab
 * view is a shareable, re-runnable reference rather than a screenshot of one.
 * Paste the link into a design review and the recipient sees the same simulation
 * — same cohort identity, same numbers — because generation is deterministic and
 * the URL carries every input that determines it.
 *
 * This is the UI-native form of the seed-stamping discipline the whole system is
 * built on: an artifact you cannot reproduce is an anecdote.
 */

export interface LabState {
  condition: string;
  seed: number;
  n: number;
  inclusion: string[];
  exclusion: string[];
}

export const DEFAULT_STATE: LabState = {
  condition: "type 2 diabetes",
  seed: 42,
  n: 400,
  inclusion: ["age >= 50"],
  exclusion: [],
};

/** Rules go in as repeated params so the URL stays readable and diffable. */
export function encodeState(state: LabState): string {
  const params = new URLSearchParams();
  params.set("condition", state.condition);
  params.set("seed", String(state.seed));
  params.set("n", String(state.n));
  state.inclusion.filter((r) => r.trim()).forEach((r) => params.append("inc", r));
  state.exclusion.filter((r) => r.trim()).forEach((r) => params.append("exc", r));
  return `?${params.toString()}`;
}

export function decodeState(search: string): LabState {
  const params = new URLSearchParams(search);
  // Number("") is 0, and 0 is finite — so an empty param would sail through as a
  // legitimate value and send cohort size 0 to the server. Treat blank as absent.
  const asNumber = (key: string, fallback: number, minimum = Number.NEGATIVE_INFINITY): number => {
    const raw = params.get(key)?.trim();
    if (!raw) return fallback;
    const parsed = Number(raw);
    return Number.isFinite(parsed) && parsed >= minimum ? parsed : fallback;
  };

  return {
    condition: params.get("condition") ?? DEFAULT_STATE.condition,
    seed: asNumber("seed", DEFAULT_STATE.seed),
    n: asNumber("n", DEFAULT_STATE.n, 1),
    inclusion: params.getAll("inc").length
      ? params.getAll("inc")
      : DEFAULT_STATE.inclusion,
    exclusion: params.getAll("exc"),
  };
}

/** Replace rather than push: typing a rule should not fill the back button. */
export function syncUrl(state: LabState): void {
  if (typeof window === "undefined") return;
  window.history.replaceState(null, "", encodeState(state));
}

export function shareableUrl(state: LabState): string {
  if (typeof window === "undefined") return encodeState(state);
  return `${window.location.origin}${window.location.pathname}${encodeState(state)}`;
}
