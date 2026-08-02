import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RuleEditor } from "./components/RuleEditor";
import { Readout } from "./components/Readout";
import { ProvenanceRail } from "./components/ProvenanceRail";
import { PreviewChannel, postPreview, type PreviewResult } from "./lib/preview";
import { decodeState, shareableUrl, syncUrl, type LabState } from "./lib/urlState";

const CONDITIONS = [
  "type 2 diabetes", "COPD", "heart failure", "breast cancer", "rheumatoid arthritis",
];

export function App() {
  const [state, setState] = useState<LabState>(() =>
    decodeState(typeof window === "undefined" ? "" : window.location.search),
  );
  const [result, setResult] = useState<PreviewResult | null>(null);
  // The last response that parsed cleanly. Figures fall back to it while the
  // editor text is broken, so a half-typed rule never shows a wrong number.
  const [lastGood, setLastGood] = useState<PreviewResult | null>(null);

  const applyResult = useCallback((next: PreviewResult) => {
    setResult(next);
    if (!next.stale) setLastGood(next);
  }, []);
  const [assumptions, setAssumptions] = useState<{ name: string; confidence: string }[]>([]);
  const [unquotable, setUnquotable] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);

  const channel = useRef<PreviewChannel | null>(null);
  if (channel.current === null) channel.current = new PreviewChannel(postPreview);

  const preview = useCallback((next: LabState) => {
    channel.current?.request(
      {
        condition: next.condition, n: next.n, seed: next.seed,
        inclusion: next.inclusion, exclusion: next.exclusion,
      },
      applyResult,
    );
  }, [applyResult]);

  // Every state change re-previews AND rewrites the URL, so the address bar is
  // always a working reference to exactly what is on screen.
  const update = useCallback((patch: Partial<LabState>) => {
    setState((current) => {
      const next = { ...current, ...patch };
      syncUrl(next);
      preview(next);
      return next;
    });
  }, [preview]);

  useEffect(() => {
    syncUrl(state);
    void channel.current?.fire(
      {
        condition: state.condition, n: state.n, seed: state.seed,
        inclusion: state.inclusion, exclusion: state.exclusion,
      },
      applyResult,
    );
    return () => channel.current?.cancel();
    // First paint only; later changes go through `update`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetch("/assumptions")
      .then((r) => r.json())
      .then((data) => {
        setAssumptions(data.assumptions ?? []);
        setUnquotable(data.unquotable ?? []);
      })
      .catch(() => undefined);
  }, []);

  const url = useMemo(() => shareableUrl(state), [state]);

  return (
    <div className="lab">
      <header className="head">
        <h1>Scenario Lab</h1>
        <span className="where">
          Eligibility updates as you type. Timeline simulation is a separate,
          explicit run — it is genuinely slower, and pretending otherwise would
          make the fast thing feel slow.
        </span>
        <div className="controls">
          <label>
            condition
            <select
              value={state.condition}
              aria-label="condition"
              onChange={(e) => update({ condition: e.target.value })}
            >
              {CONDITIONS.map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          <label>
            seed
            <input
              type="number" value={state.seed} aria-label="seed"
              onChange={(e) => update({ seed: Number(e.target.value) || 0 })}
            />
          </label>
          <label>
            n
            <input
              type="number" value={state.n} aria-label="cohort size"
              onChange={(e) => update({ n: Number(e.target.value) || 1 })}
            />
          </label>
        </div>
      </header>

      <section className="col rules">
        <RuleEditor
          title="Inclusion" kind="inclusion" rules={state.inclusion}
          diagnostics={result?.diagnostics ?? []}
          onChange={(inclusion) => update({ inclusion })}
        />
        <RuleEditor
          title="Exclusion" kind="exclusion" rules={state.exclusion}
          diagnostics={result?.diagnostics ?? []}
          onChange={(exclusion) => update({ exclusion })}
        />
      </section>

      <section className="col readout">
        <Readout result={result} lastGood={lastGood} />
      </section>

      <aside className="col rail">
        <ProvenanceRail
          state={state} result={result}
          assumptions={assumptions} unquotable={unquotable}
        />
      </aside>

      <footer className="share">
        <label htmlFor="share-url">Reproducible link</label>
        <code id="share-url" data-testid="share-url">{url}</code>
        <button
          type="button"
          onClick={() => {
            void navigator.clipboard?.writeText(url);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </footer>
    </div>
  );
}
