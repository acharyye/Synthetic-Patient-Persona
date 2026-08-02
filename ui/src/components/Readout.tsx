import type { PreviewResult } from "../lib/preview";

/**
 * The attrition readout. Numbers are the product, so they are the typography:
 * monospace, tabular figures, set large and tight like an instrument display.
 *
 * `sole_reason` is given its own column because it is the actionable number —
 * personas who would have qualified but for that one line.
 */
interface Props {
  result: PreviewResult | null;
  /** Latest result that parsed cleanly. Figures come from here while the
   *  current text is broken — see below. */
  lastGood?: PreviewResult | null;
}

export function Readout({ result, lastGood = null }: Props) {
  if (!result) {
    return (
      <div>
        <h2>Eligibility</h2>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>Waiting for first pass…</p>
      </div>
    );
  }

  // While the text is broken, show the last figures that were actually TRUE —
  // not the server's score for the surviving subset. Breaking your only rule
  // would otherwise make eligibility appear to jump to 100%, which is a wrong
  // number presented as the current state. Diagnostics still come from the
  // latest response, so the editor stays live.
  const figures = result.stale && lastGood ? lastGood : result;
  const rate = (figures.eligibility_rate * 100).toFixed(1);

  return (
    <div className={result.stale ? "stale" : undefined}>
      <h2>Eligibility</h2>

      <div className="figure">
        <span className="big" data-testid="eligible-count">
          {figures.eligible}
        </span>
        <span className="of">
          of <span className="num">{figures.screened}</span> screened ·{" "}
          <span className="num" data-testid="eligibility-rate">
            {rate}%
          </span>
        </span>
      </div>

      {result.stale && (
        <p className="stale-note" role="status" data-testid="stale-note">
          <strong>Stale.</strong>
          <span>{result.stale_reason}</span>
        </p>
      )}

      <h2>Per-rule attrition</h2>
      <table className="impact">
        <thead>
          <tr>
            <th>Criterion</th>
            <th>Kind</th>
            <th className="r">Screens out</th>
            <th className="r">Sole reason</th>
            <th className="r">Shapley</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {figures.attribution.length === 0 && (
            <tr>
              <td colSpan={6} style={{ color: "var(--muted)" }}>
                No rules yet — everyone is eligible.
              </td>
            </tr>
          )}
          {figures.attribution.map((rule) => (
            <tr key={rule.criterion}>
              <td className="crit">{rule.criterion}</td>
              <td style={{ color: "var(--muted)" }}>{rule.kind}</td>
              <td className="r num">{rule.screened_out}</td>
              <td className="r num">{rule.sole_reason}</td>
              <td className="r num">{(rule.shapley_share * 100).toFixed(1)}%</td>
              <td>
                <span
                  className="share-bar"
                  style={{ width: `${Math.max(2, rule.shapley_share * 90)}px` }}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
