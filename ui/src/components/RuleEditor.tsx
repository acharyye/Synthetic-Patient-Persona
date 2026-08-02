import type { Diagnostic } from "../lib/preview";

interface Props {
  title: string;
  kind: "inclusion" | "exclusion";
  rules: string[];
  diagnostics: Diagnostic[];
  onChange: (rules: string[]) => void;
}

/**
 * Rules as editable lines with inline diagnostics.
 *
 * A rule that fails to parse gets the integrity treatment — the same red as a
 * never-quote assumption — because a rule that cannot be read is a rule that
 * cannot be trusted. But the preview beside it keeps its last-valid numbers:
 * being mid-keystroke is not an error state.
 */
export function RuleEditor({ title, kind, rules, diagnostics, onChange }: Props) {
  const problemFor = (text: string): Diagnostic | undefined =>
    diagnostics.find((d) => !d.ok && d.kind === kind && d.text === text);

  const update = (index: number, value: string) => {
    const next = [...rules];
    next[index] = value;
    onChange(next);
  };

  return (
    <div className="rule-group">
      <h2>{title}</h2>
      {rules.map((rule, index) => {
        const problem = problemFor(rule);
        return (
          <div key={index}>
            <div className={`rule-row${problem ? " invalid" : ""}`}>
              <input
                value={rule}
                aria-label={`${kind} rule ${index + 1}`}
                aria-invalid={problem ? true : undefined}
                spellCheck={false}
                placeholder={kind === "inclusion" ? "age >= 50" : "CKD"}
                onChange={(event) => update(index, event.target.value)}
              />
              <button
                type="button"
                aria-label={`Remove ${kind} rule ${index + 1}`}
                onClick={() => onChange(rules.filter((_, i) => i !== index))}
              >
                ×
              </button>
            </div>
            {problem && (
              <p className="diag" role="status">
                {problem.message}
              </p>
            )}
          </div>
        );
      })}
      <button type="button" className="add" onClick={() => onChange([...rules, ""])}>
        + Add {kind} rule
      </button>
    </div>
  );
}
