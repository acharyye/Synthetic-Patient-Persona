"""Generate the authoring worksheet for the battery's citation expectations.

    PYTHONPATH=src python scripts/state_dumps.py > state_dumps_for_authoring.md

The output is gitignored: it is a **worksheet, not source**, regenerable from the
battery and the cohort at any time. What is committed is the authored
expectations in `tests/eval/narration_battery.json`.

The protocol this exists to serve (`tests/eval/v3_expected_shape.json`,
`authoring_protocol`): expectations are authored **blind from state dumps** —
profile, derived barriers, journey, and what retrieval offers — and never from
recorded takes. Authoring from model output measures stability rather than
relevance; it is the trap this eval already fell into once, and it is most
seductive when the takes are fresh and good.

So this script deliberately shows only inputs. It does not read a cassette, and
it must not learn to.
"""
from __future__ import annotations

import sys
from datetime import date

from spp.cohort import generate_cohort
from spp.knowledge import load_graph, retrieve
from spp.narration.evaluation import expectations, load_battery
from spp.narration.state_facts import derive_state_facts

AS_OF = date(2026, 8, 1)
CONDITIONS = ["type 2 diabetes", "COPD", "heart failure",
              "breast cancer", "rheumatoid arthritis"]


def build_cohort():
    people = []
    for condition in CONDITIONS:
        people.extend(generate_cohort(condition, 6, seed=42, as_of=AS_OF))
    return people


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    only = argv[0] if argv else None

    graph = load_graph()
    by_key = {(p.condition, p.patient_id): p for p in build_cohort()}
    battery = load_battery()

    print("# State dumps for authoring — v3 citation expectations")
    print()
    print("Inputs only. No recorded take appears here, by design.")
    print()

    seen: set[tuple[str, str]] = set()
    for case in battery:
        key = (case["condition"], case["patient_id"])
        if only and case["condition"] != only:
            continue
        dna = by_key[key]

        if key not in seen:
            seen.add(key)
            state = derive_state_facts(dna)
            print(f"\n## {dna.patient_id} — {dna.condition}")
            print(f"\n{dna.context()}\n")
            for namespace in ("P", "B", "J"):
                facts = [f for f in state.facts if f.namespace == namespace]
                if not facts:
                    continue
                print(f"**{namespace}-**")
                for fact in facts:
                    print(f"- `{fact.id}` — {fact.text}")
                print()

        must, may = expectations(case)
        tag = case["id"].split("-")[1]
        barriers = tuple(b.name for b in dna.barriers)
        result = retrieve(graph, dna.condition, case["question"],
                          limit=case.get("limit", 16), barriers=barriers)

        print(f"### CASE `{case['id']}` [{tag}]")
        print(f"\n> {case['question']}\n")
        print("Retrieved, in rank order:")
        for rank, fact in enumerate(result.facts):
            print(f"{rank:>3}. `{fact.id}` {fact.text}")
        inherited = [i for group in must for i in group]
        print(f"\nInherited expectation (REVIEW, do not inherit): {inherited}")
        if may:
            print(f"Current may-set: {list(may)}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
