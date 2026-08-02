/**
 * Component tests fed by the SAME committed fixtures the Python tests read.
 *
 * The two renderers share no code — deliberately. Shared rendering logic across
 * Python and TypeScript would be a maintenance tax for no benefit. Shared
 * FIXTURES are the right coupling: neither renderer can silently disagree with
 * the other about a number, because both assert against the same bytes.
 *
 * Regenerate with: PYTHONPATH=src python scripts/export_schema.py
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Readout } from "../src/components/Readout";
import { RuleEditor } from "../src/components/RuleEditor";
import { ProvenanceRail } from "../src/components/ProvenanceRail";
import type { PreviewResult } from "../src/lib/preview";
import clean from "../../tests/fixtures/scenario_preview.json";
import withErrors from "../../tests/fixtures/scenario_preview_with_errors.json";

const cleanResult = clean as unknown as PreviewResult;
const errorResult = withErrors as unknown as PreviewResult;

describe("Readout renders exactly what the server computed", () => {
  it("shows the server's eligible count and rate", () => {
    render(<Readout result={cleanResult} />);
    expect(screen.getByTestId("eligible-count").textContent)
      .toBe(String(cleanResult.eligible));
    expect(screen.getByTestId("eligibility-rate").textContent)
      .toBe(`${(cleanResult.eligibility_rate * 100).toFixed(1)}%`);
  });

  it("lists every criterion the server attributed", () => {
    render(<Readout result={cleanResult} />);
    for (const rule of cleanResult.attribution) {
      expect(screen.getByText(rule.criterion)).toBeInTheDocument();
    }
  });

  it("surfaces sole_reason — the actionable number", () => {
    render(<Readout result={cleanResult} />);
    expect(screen.getByText("Sole reason")).toBeInTheDocument();
  });

  it("invents no numbers when there are no rules", () => {
    render(<Readout result={{ ...cleanResult, attribution: [] }} />);
    expect(screen.getByText(/everyone is eligible/i)).toBeInTheDocument();
  });
});

describe("stale state keeps the last valid numbers", () => {
  it("marks stale without blanking the readout", () => {
    // The fixture is a real response to a half-typed rule.
    expect(errorResult.stale).toBe(true);
    render(<Readout result={errorResult} />);

    expect(screen.getByTestId("stale-note")).toBeInTheDocument();
    expect(screen.getByTestId("eligible-count").textContent)
      .toBe(String(errorResult.eligible));
    expect(Number(screen.getByTestId("eligible-count").textContent)).toBeGreaterThan(0);
  });

  it("shows the server's explanation rather than a generic error", () => {
    render(<Readout result={errorResult} />);
    expect(screen.getByTestId("stale-note").textContent)
      .toContain(errorResult.stale_reason.slice(0, 30));
  });

  it("a clean result carries no stale marker", () => {
    render(<Readout result={cleanResult} />);
    expect(screen.queryByTestId("stale-note")).toBeNull();
  });
});

describe("RuleEditor shows diagnostics inline", () => {
  it("flags the offending rule and explains why", () => {
    const bad = errorResult.diagnostics.find((d) => !d.ok)!;
    render(
      <RuleEditor
        title="Inclusion" kind="inclusion"
        rules={["age >= 50", bad.text]}
        diagnostics={errorResult.diagnostics}
        onChange={() => undefined}
      />,
    );
    expect(screen.getByText(bad.message)).toBeInTheDocument();
    const input = screen.getByLabelText("inclusion rule 2");
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("leaves valid rules unmarked", () => {
    render(
      <RuleEditor
        title="Inclusion" kind="inclusion" rules={["age >= 50"]}
        diagnostics={errorResult.diagnostics} onChange={() => undefined}
      />,
    );
    expect(screen.getByLabelText("inclusion rule 1"))
      .not.toHaveAttribute("aria-invalid");
  });
});

describe("provenance is primary interface", () => {
  const assumptions = [
    { name: "timeline.dropout_hazard", confidence: "expert_guess" },
    { name: "cohort.correlation_psd_gate", confidence: "measured" },
  ];

  it("renders seed, cohort identity and pack version as standing furniture", () => {
    render(
      <ProvenanceRail
        state={{ condition: "type 2 diabetes", seed: 42, n: 200, inclusion: [], exclusion: [] }}
        result={cleanResult} assumptions={assumptions}
        unquotable={["timeline.dropout_hazard"]}
      />,
    );
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText(cleanResult.cohort.identity)).toBeInTheDocument();
    expect(screen.getByText(cleanResult.cohort.identity).textContent).toContain("@v");
  });

  it("marks never-quote assumptions unmistakably", () => {
    render(
      <ProvenanceRail
        state={{ condition: "COPD", seed: 1, n: 10, inclusion: [], exclusion: [] }}
        result={cleanResult} assumptions={assumptions}
        unquotable={["timeline.dropout_hazard"]}
      />,
    );
    expect(screen.getByText("never quote")).toBeInTheDocument();
    expect(screen.getByText(/1 never quote/)).toBeInTheDocument();
  });
});

describe("last-good figures while the text is broken", () => {
  it("keeps the last TRUE numbers rather than scoring the surviving subset", () => {
    // Breaking your only rule leaves zero rules parsing, so the server honestly
    // reports everyone eligible. Rendering that would show eligibility jumping
    // to 100% mid-keystroke — a wrong number presented as current state.
    const broken = { ...errorResult, eligible: 400, screened: 400, eligibility_rate: 1 };
    render(<Readout result={broken} lastGood={cleanResult} />);

    expect(screen.getByTestId("eligible-count").textContent)
      .toBe(String(cleanResult.eligible));
    expect(screen.getByTestId("stale-note")).toBeInTheDocument();
  });

  it("still shows the latest diagnostics while holding old figures", () => {
    render(<Readout result={errorResult} lastGood={cleanResult} />);
    expect(screen.getByTestId("stale-note").textContent)
      .toContain(errorResult.stale_reason.slice(0, 20));
  });

  it("falls back to the current result when there is no good one yet", () => {
    render(<Readout result={errorResult} lastGood={null} />);
    expect(screen.getByTestId("eligible-count").textContent)
      .toBe(String(errorResult.eligible));
  });

  it("a clean result always renders its own figures", () => {
    render(<Readout result={cleanResult} lastGood={errorResult} />);
    expect(screen.getByTestId("eligible-count").textContent)
      .toBe(String(cleanResult.eligible));
  });
});
