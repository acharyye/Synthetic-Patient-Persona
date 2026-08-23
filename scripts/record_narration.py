"""First live run: score the compliance battery and record gated cassettes.

    # one-time
    brew install ollama && ollama serve &
    ollama pull qwen2.5:7b-instruct

    SPP_LIVE=true PYTHONPATH=src python scripts/record_narration.py --canary
    SPP_LIVE=true PYTHONPATH=src python scripts/record_narration.py --record

`--canary` first, always. It scores the battery against deliberately degraded
configurations and refuses to proceed unless the scores fall — an eval that
cannot fail is not evidence, and a compliance number from an insensitive
instrument is worse than no number because it looks like reassurance.

`--record` then runs the battery live and writes cassettes, but only for
responses that pass the citation gate. Failures land in a quarantine file with
their reason; that file IS the compliance dataset, and its size relative to the
cassette is the headline result.

READING PROTOCOL — pre-committed, before any number exists. Do not act on the
aggregates until you have read, in full:

  * the 5 sampled raw takes printed at the end (chosen by seed, so the sample is
    not cherry-picked), and
  * every entry in the quarantine file.

No metric here catches DEGENERACY. A model that answers every question with one
short factual segment citing one correct fact scores citation-validity 1.0 and
can clear recall on the easy questions while being useless as a persona voice.
`mean_segments_per_take`, `mean_response_chars` and `single_segment_rate` support
the eye; they do not replace it.

Nothing here is required for the offline test suite to pass. It exists so the
first contact with a real model happens against a pipeline where malformed
citations are ungrammatical, bad recordings cannot persist, and the measuring
instrument has already been tested.
"""
from __future__ import annotations

import argparse
import json
from datetime import date

from spp.assumptions import NARRATION_MODEL
from spp.cohort import generate_cohort
from spp.config import settings
from spp.knowledge import load_graph
from spp.narration.cassette import (
    CASSETTE_DIR,
    CONTEXT_OVERFLOW_REASON,
    GatedRecorder,
    archive_cassette,
)
from spp.narration.bundle import BundleManifest, write_bundle
from spp.narration.evaluation import grade, load_battery, run_canary, score
from spp.narration.prompt import PROMPT_VERSION
from spp.narration.sampling import (
    DEFAULT_SAMPLING,
    context_fits,
    model_identity,
    model_is_resident,
    resolve_model_digest,
    warm_up,
)
from spp.narration.structured import check_structured, parse_structured

AS_OF = date(2026, 8, 1)
CONDITIONS = ["type 2 diabetes", "COPD", "heart failure",
              "breast cancer", "rheumatoid arthritis"]


def build_cohort():
    people = []
    for condition in CONDITIONS:
        people.extend(generate_cohort(condition, 6, seed=42, as_of=AS_OF))
    return people


def live_generator(sampling=DEFAULT_SAMPLING):
    """A generate(prompt, schema, repair) that calls the configured backend.

    Guards the context window before every call. Ollama truncates the prompt head
    silently when it overflows, which downstream is indistinguishable from a
    starved-context degradation — so an overflow is refused here rather than
    generated and scored.
    """
    from spp.foundation.llm import generate as llm_generate

    def generate(prompt, schema, repair):
        system = prompt.system
        if repair:
            system = f"{system}\n\nCORRECTION: {repair}"

        fits, estimated = context_fits(system, prompt.user, sampling)
        if not fits:
            raise ContextTooLong(estimated)

        result = llm_generate(system, prompt.user, max_tokens=sampling.num_predict,
                              schema=schema, options=sampling.as_options())
        if result.synthetic:
            raise RuntimeError(
                "the null backend answered — set SPP_LIVE=true and configure "
                "llm_backend before recording"
            )
        return result.text

    return generate


def _canary_path(release: str):
    from spp.narration.bundle import EVIDENCE_DIR

    return EVIDENCE_DIR / release / "_canary.json"


def _stash_canary(release: str, result: dict) -> None:
    """Keep the canary result so --record can fold it into the bundle."""
    path = _canary_path(release)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "sensitive": result["sensitive"],
        "verdict": result["verdict"],
        "detected": result["detected"],
        "lever_metric": result["lever_metric"],
        "state_lever_clean": result["state_lever_clean"],
        "baseline": result["baseline"].model_dump(exclude={"results"}),
        "degraded": {k: v.model_dump(exclude={"results"})
                     for k, v in result["degraded"].items()},
    }, indent=2, default=str) + "\n", encoding="utf-8")


def _load_canary(release: str, key: str | None = None):
    path = _canary_path(release)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get(key) if key else payload


class ContextTooLong(RuntimeError):
    def __init__(self, estimated: int) -> None:
        super().__init__(f"prompt ~{estimated} tokens exceeds the context budget")
        self.estimated = estimated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canary", action="store_true",
                        help="verify the eval can detect degradation, then stop")
    parser.add_argument("--rerecord", action="store_true",
                        help="archive the existing cassette, then record fresh. "
                             "REQUIRED after a PROMPT_VERSION bump: the recorder "
                             "refuses to append to recordings made under a different "
                             "prompt, and archiving keeps that refusal deliberate "
                             "instead of improvised.")
    parser.add_argument("--record", action="store_true",
                        help="run the battery live and write gated cassettes")
    parser.add_argument("--name", default="narration_battery")
    parser.add_argument("--release", default="v0.1",
                        help="release the evidence bundle is pinned to")
    args = parser.parse_args(argv)

    if not (args.canary or args.record):
        parser.error("choose --canary or --record")

    model = NARRATION_MODEL.params["model"]
    sampling = DEFAULT_SAMPLING

    # Pin by digest. A tag is a mutable pointer: a registry update can change the
    # weights and the quantization under the same name.
    digest = resolve_model_digest(model)
    if digest is None and args.record:
        print(f"could not resolve a digest for {model!r} — is Ollama running?")
        print("Refusing to record: a cassette that cannot name its weights is "
              "not evidence about a model.")
        return 1

    print(f"backend={settings.llm_backend} model={model_identity(model, digest)}")
    print(f"prompt_version={PROMPT_VERSION} live={settings.spp_live}")
    print(f"sampling={sampling.as_options()}")

    # Every run starts WARM. A cold load and a warm one produce different output
    # for identical inputs (see sampling.model_is_resident), each state exact in
    # itself — so the load state is a hidden variable, and two bundles that
    # disagree on it are not comparable. Forcing it beats stamping it: stamping
    # would only tell a reader the comparison is invalid.
    was_resident = model_is_resident(model)
    if was_resident is False:
        print("model not resident — warming up so this run is comparable to the "
              "others...")
    if not warm_up(model, sampling):
        print("could not warm the model; refusing to run against an unknown "
              "load state.")
        return 1
    print(f"load_state=warm (was_resident={was_resident})")

    graph = load_graph()
    cohort = build_cohort()
    battery = load_battery()
    generate = live_generator(sampling)

    if args.canary:
        print(f"\nrunning canary over {len(battery)} cases...")
        result = run_canary(cohort, generate, graph=graph, battery=battery, model=model)
        print("\n  " + result["baseline"].headline())
        for lever, report in result["degraded"].items():
            moved = "detected" if result["detected"][lever] else "NOT detected"
            print(f"  {report.headline()}   [{moved}]")
        baseline = result["baseline"]
        print(f"\nVERDICT: {result['verdict']}")
        _stash_canary(args.release, result)

        if not result["state_lever_clean"]:
            # Pre-registered note: F-recall should be roughly unchanged when the
            # state ids are removed. If it moves too, the lever is changing more
            # than one thing and its collapse is not evidence about state ids.
            stripped = result["degraded"]["strip_state_ids"]
            print("\nWARNING: the strip_state_ids lever is NOT clean — "
                  f"f_recall moved from {baseline.f_recall:.0%} to "
                  f"{stripped.f_recall:.0%}, and f_recall_exclusive (groups no "
                  "state id can satisfy) moved "
                  f"{baseline.f_recall_exclusive:.0%} -> "
                  f"{stripped.f_recall_exclusive:.0%}, drift "
                  f"{result['f_recall_exclusive_drift']:.2f}.")
            if result["f_recall_exclusive_drift"] > 0.05:
                print("  The exclusive figure moves too, so this is NOT a mixed "
                      "alternation being grounded through its profile member "
                      "instead of its graph one. State ids are DISPLACING graph "
                      "citations for claims with no other citation path — the "
                      "enum-incentive finding f_recall_holds_independently was "
                      "registered to catch. Record it as a finding; do not read "
                      "state_coverage as free of it.")

        if not result["sensitive"]:
            if not result["detected"]["strip_state_ids"]:
                print("\nThe state lever did not fire: removing the P/B/J ids "
                      f"left state_coverage at "
                      f"{result['degraded']['strip_state_ids'].state_coverage:.0%} "
                      f"against a baseline of {baseline.state_coverage:.0%}. "
                      "The v3 axis cannot be measured until it can fail.")
            # The canary has TWO readings once a live model is involved. It
            # asserts degraded < normal; if the model is non-compliant
            # everywhere, both score low and the gap vanishes. Disambiguate on
            # the normal-config absolute scores before triaging.
            print("\nDISAMBIGUATION — 'insensitive' has two causes:")
            print(f"  normal-config citation_validity {baseline.citation_validity:.0%}, "
                  f"coverage {baseline.factual_coverage:.0%}, "
                  f"hard failures {baseline.hard_failure_rate:.0%}")
            if baseline.hard_failure_rate > 0.5 or baseline.factual_coverage < 0.5:
                print("  -> normal config scores LOW: this is a MODEL question. "
                      "The record refusal did its job for the right reason; "
                      "iterate the prompt before trusting any comparison.")
            else:
                print("  -> normal config scores HIGH but the gap vanished: this "
                      "is an INSTRUMENT question. The degradation levers are not "
                      "biting; fix the eval before reading its numbers.")
            print("\nRefusing to record.")
            return 1
        return 0

    if args.rerecord:
        archived = archive_cassette(args.name)
        if archived:
            print(f"archived previous cassette -> {archived}")
        else:
            print("no previous cassette to archive")

    print(f"\nrecording {len(battery)} cases...")
    recorder = GatedRecorder(args.name, backend=settings.llm_backend, model=model,
                             prompt_version=PROMPT_VERSION,
                             model_digest=digest or "",
                             sampling=sampling.stamp())

    report = score(cohort, generate, graph=graph, battery=battery,
                   label="live", model=model)

    # Re-run to capture the raw exchanges for the cassette, gating each one.
    from spp.knowledge.retrieval import retrieve
    from spp.narration.prompt import build_prompt
    from spp.narration.structured import answer_schema

    by_id = {dna.patient_id: dna for dna in cohort}
    for case in battery:
        dna = by_id.get(case["patient_id"]) or cohort[0]
        retrieval = retrieve(graph, dna.condition, case["question"],
                             limit=case.get("limit", 16),
                             barriers=tuple(b.name for b in dna.barriers))
        prompt = build_prompt(dna, retrieval, case["question"])
        schema = answer_schema(prompt.allowed_fact_ids)

        try:
            raw = generate(prompt, schema, None)
        except ContextTooLong as exc:
            # Its own reason, so a truncation refusal is never counted as the
            # model failing to ground.
            recorder.offer(prompt.fingerprint, prompt.system, prompt.user, "",
                           passed=False,
                           reason=f"{CONTEXT_OVERFLOW_REASON}: {exc}")
            continue

        answer = parse_structured(raw)
        check = (
            check_structured(answer, prompt.allowed_fact_ids) if answer else None
        )
        recorder.offer(
            prompt.fingerprint, prompt.system, prompt.user, raw,
            passed=bool(check and check.ok),
            reason=(check.summary if check else "unparseable response"),
        )

    paths = recorder.save()
    verdict = grade(report)

    print("\n  " + report.headline())
    print(f"  overall {report.overall:.3f}")
    print(f"\n  position concentration (top-2): {report.position_concentration:.0%}")
    print(f"  factual-segment fraction by question: {report.factual_fraction_by_tag}")

    print(f"\nGRADED against bars registered {verdict.registered_on} "
          f"(before first live run: {verdict.registered_before_first_live_run})")
    for bar in verdict.bars:
        mark = "PASS" if bar.passed else "MISS"
        print(f"  [{mark}] {bar.kind:<4} {bar.metric:<22} "
              f"observed {bar.observed:.3f} vs bar {bar.bar}")
    print(f"\n  {verdict.next_action()}")

    # Degeneracy support, then the mandatory read.
    print(f"\n  segments/take {report.mean_segments_per_take}, "
          f"chars/response {report.mean_response_chars}, "
          f"single-segment {report.single_segment_rate:.0%}")
    if report.single_segment_rate > 0.5:
        print("  WARNING: over half the answers are a single segment — check for "
              "degeneracy before believing the validity score.")

    import random as _random

    sample = _random.Random(sampling.seed).sample(
        report.results, min(5, len(report.results))
    )

    print("\n" + "=" * 70)
    print("READ THESE BEFORE ACTING ON THE AGGREGATES (pre-committed protocol)")
    print("=" * 70)
    for case in sample:
        print(f"\n[{case.case_id}] {case.question}")
        print(f"  segments={case.total_segments} factual={case.factual_segments} "
              f"cited={case.cited} grounded={case.grounded}")
        for seg in case.segments:
            print(f"    [{seg['kind']:8}] {seg['text']}")
            print(f"               -> {seg['fact_ids']}")
    print(f"\n  quarantine entries to read in full: {recorder.rejected}")
    if paths["quarantine"]:
        print(f"  {paths['quarantine']}")
    print(f"\n  accepted {recorder.accepted}, quarantined {recorder.rejected}, "
          f"compliance {recorder.compliance_rate}")
    print(f"  cassette:   {paths['cassette']}")
    print(f"  quarantine: {paths['quarantine'] or '(none — everything passed)'}")

    # Archive before printing the read-me-first block, so the bundle exists even
    # if the session is interrupted at the reading step.
    bundle = write_bundle(
        release=args.release,
        manifest=BundleManifest(
            release=args.release, backend=settings.llm_backend, model=model,
            model_digest=digest or "", prompt_version=PROMPT_VERSION,
            sampling=sampling.stamp(), battery_cases=len(battery),
            accepted_takes=recorder.accepted, quarantined_takes=recorder.rejected,
            compliance_rate=recorder.compliance_rate,
            canary_sensitive=_load_canary(args.release, "sensitive"),
            bars_passed=verdict.passed,
        ),
        canary=_load_canary(args.release),
        compliance={"report": report.model_dump(exclude={"results"}),
                    "verdict": verdict.model_dump(),
                    "quarantine_reasons": recorder.reason_counts()},
        sampled_takes=[case.model_dump() for case in sample],
        quarantine=[q.model_dump() for q in recorder.quarantine],
    )
    print(f"\n  evidence bundle: {bundle}")

    summary = CASSETTE_DIR / f"{args.name}.compliance.json"
    summary.write_text(json.dumps({
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "backend": settings.llm_backend,
        "model_digest": digest,
        "sampling": sampling.stamp(),
        "report": report.model_dump(exclude={"results"}),
        "compliance_rate": recorder.compliance_rate,
        "quarantine_reasons": recorder.reason_counts(),
        "verdict": verdict.model_dump(),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"  compliance: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
