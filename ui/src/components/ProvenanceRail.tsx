import type { PreviewResult } from "../lib/preview";
import type { LabState } from "../lib/urlState";

interface Assumption {
  name: string;
  confidence: string;
}

interface Props {
  state: LabState;
  result: PreviewResult | null;
  assumptions: Assumption[];
  unquotable: string[];
}

/**
 * The provenance rail — a permanent column, never a footer or a tooltip.
 *
 * This is the design's one real commitment. Four phases went into making every
 * number traceable to a seed, a pack version and a ledger entry; if that
 * evidence renders as chrome at the bottom of the page, the interface is
 * asserting the opposite of what the system guarantees.
 */
export function ProvenanceRail({ state, result, assumptions, unquotable }: Props) {
  const unquotableSet = new Set(unquotable);

  return (
    <div>
      <h2>Provenance</h2>
      <div className="stamp">
        <Row k="condition" v={state.condition} />
        <Row k="seed" v={String(state.seed)} />
        <Row k="cohort size" v={String(state.n)} />
        <Row k="identity" v={result?.cohort.identity ?? "—"} />
        <Row k="resident" v={result ? (result.cohort.cached ? "cached" : "generated") : "—"} />
      </div>

      <h2>
        Assumptions · {assumptions.length}
        {unquotable.length > 0 && (
          <span style={{ color: "var(--integrity)" }}> · {unquotable.length} never quote</span>
        )}
      </h2>
      <div data-testid="ledger">
        {assumptions.map((assumption) => (
          <div className="ledger-line" key={assumption.name}>
            <span className="name">{assumption.name}</span>
            {unquotableSet.has(assumption.name) ? (
              <span className="tag never">never quote</span>
            ) : (
              <span className="tag ok">{assumption.confidence}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="stamp-row">
      <span className="k">{k}</span>
      <span className="v">{v}</span>
    </div>
  );
}
