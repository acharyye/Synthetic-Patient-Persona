"""Export artifact models to JSON Schema and generate committed TypeScript types.

    PYTHONPATH=src python scripts/export_schema.py

This is the SPA's contract suite. The generated `.ts` file is **committed**, so a
Pydantic change that alters an artifact shows up as a visible diff and then as a
TypeScript compile error — never as a runtime surprise in a design review.

It also writes **shared fixtures**: real artifacts, committed once, read by both
the Python renderer tests and the SPA component tests. That is the right coupling
between the two renderers. Sharing rendering *logic* across Python and TS would
be a maintenance tax for no benefit; sharing *fixtures* means the two can never
silently disagree about a number even though they share no code.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TYPES_DIR = ROOT / "ui" / "src" / "types"
FIXTURE_DIR = ROOT / "tests" / "fixtures"

HEADER = """// GENERATED — do not edit by hand.
// Source: Pydantic models in src/spp/, exported by scripts/export_schema.py.
//
// This file is committed on purpose. It is the SPA's contract with the server:
// a schema change becomes a reviewable diff and then a compile error, instead of
// a field that is silently undefined in front of an audience.
"""


def export_schema() -> Path:
    from spp.narration.interview import InterviewTurn
    from spp.narration.panel import PanelStatement, PanelTranscript, Theme
    from spp.protocol.attribution import EligibilityAttribution, RuleAttribution
    from spp.protocol.lenient import CriterionDiagnostic, LenientParse
    from spp.schemas import PatientDNA
    from spp.simulation.counterfactual import DiffResult, Flip
    from spp.simulation.report import DiffReport

    models = {
        "DiffReport": DiffReport, "DiffResult": DiffResult, "Flip": Flip,
        "EligibilityAttribution": EligibilityAttribution,
        "RuleAttribution": RuleAttribution,
        "LenientParse": LenientParse, "CriterionDiagnostic": CriterionDiagnostic,
        "InterviewTurn": InterviewTurn, "PanelTranscript": PanelTranscript,
        "PanelStatement": PanelStatement, "Theme": Theme, "PatientDNA": PatientDNA,
    }
    # Pydantic nests referenced models under each schema's `$defs`, but our
    # ref_template points at a single top-level `definitions`. Hoist them, or
    # every nested type (RunProvenance, BurdenVector, ...) is a dangling $ref.
    definitions: dict = {}
    for name, model in models.items():
        schema = model.model_json_schema(ref_template="#/definitions/{model}")
        for nested_name, nested in schema.pop("$defs", {}).items():
            definitions.setdefault(nested_name, nested)
        definitions[name] = schema

    payload = {
        "$comment": (
            "GENERATED from Pydantic models. Committed so schema drift is a "
            "visible diff and a compile error, never a runtime surprise."
        ),
        "definitions": definitions,
    }
    TYPES_DIR.mkdir(parents=True, exist_ok=True)
    path = TYPES_DIR / "artifacts.schema.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def generate_types(schema_path: Path) -> Path:
    """Codegen TS from the JSON Schema via json-schema-to-typescript."""
    output = TYPES_DIR / "artifacts.ts"
    try:
        result = subprocess.run(
            ["npx", "--yes", "json-schema-to-typescript@15",
             str(schema_path), "--no-additionalProperties", "--unreachableDefinitions"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=300,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"[schema] codegen unavailable ({exc}); schema still exported")
        return output

    if result.returncode != 0:
        print(f"[schema] codegen failed:\n{result.stderr[:800]}")
        return output

    output.write_text(HEADER + "\n" + result.stdout)
    return output


def write_fixtures() -> list[Path]:
    """Commit real artifacts for BOTH test suites to read.

    Shared fixtures rather than shared code: the Python and TS renderers stay
    independent, but they cannot diverge on a number, because they assert against
    the same bytes.
    """
    from fastapi.testclient import TestClient

    from spp.api.main import app

    client = TestClient(app)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    cases = {
        "counterfactual_run.json": ("/counterfactual/run", {
            "condition": "type 2 diabetes", "n": 120, "seed": 42,
            "inclusion": ["age >= 50"], "burden": {"visits_per_year": 12},
            "remote_visits": ["v001", "v003", "v005"],
        }),
        "scenario_preview.json": ("/scenario/preview", {
            "condition": "type 2 diabetes", "n": 200, "seed": 42,
            "inclusion": ["age >= 50", "biomarkers.HbA1c_pct >= 7.5"],
            "exclusion": ["CKD"], "sequence": 1,
        }),
        "scenario_preview_with_errors.json": ("/scenario/preview", {
            "condition": "type 2 diabetes", "n": 200, "seed": 42,
            "inclusion": ["age >= 50", "bmi_at_screening > 30"], "sequence": 2,
        }),
        "panel.json": ("/panel/run", {
            "condition": "type 2 diabetes", "n": 6,
            "topic": "Could you attend the clinic twice a month?",
        }),
        "interview.json": ("/persona/narrate", {
            "condition": "COPD",
            "question": "What side effects should I expect from treatment?",
        }),
    }

    for filename, (route, body) in cases.items():
        response = client.post(route, json=body)
        response.raise_for_status()
        payload = response.json()
        # Wall-clock stamps would make the fixture churn on every regeneration.
        if isinstance(payload.get("provenance"), dict):
            payload["provenance"]["generated_at"] = "FIXTURE"
        path = FIXTURE_DIR / filename
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        written.append(path)

    return written


def main() -> int:
    schema = export_schema()
    print(f"schema    -> {schema.relative_to(ROOT)}")

    types = generate_types(schema)
    if types.exists():
        print(f"types     -> {types.relative_to(ROOT)}")

    for path in write_fixtures():
        print(f"fixture   -> {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
