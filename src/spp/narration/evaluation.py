"""Narration compliance eval: the measuring instrument, and its canary.

Scores a fixed battery of questions against a specific `(prompt_version,
model_id, adapter_version)`. Compliance numbers that are not attached to a
configuration are anecdotes, so every result carries all three.

Metrics:

  citation_validity   fraction of answers citing only ids that were offered
  factual_coverage    fraction of factual segments carrying >= 1 citation
  system_recall       cited & expected / expected           (end-to-end)
  model_recall        cited & (expected & retrieved) / (expected & retrieved)
                      Split deliberately: retrieval is deterministic and
                      separately evaluated, so a system miss with a model pass
                      means retrieval never surfaced the fact — iterate the
                      intent scorer, not the prompt. Without the split you can
                      burn prompt revisions on a retrieval failure.
  state_coverage      fraction of CIRCUMSTANTIAL segments carrying >= 1 P/B/J
                      id. New in v3, and the metric the state-citation claim has
                      to be caused BY: factual_fraction recovering WITHOUT state
                      ids present is the over-correction signature, which no
                      other metric here can tell from a real recovery.
  retry_rate          fraction needing the one permitted regeneration
  hard_failure_rate   fraction still ungrounded after that retry

**The canary matters more than the metrics.** A retrieval eval authored from
system output once measured stability while retrieval ignored the query
entirely — a green instrument reading a broken system. So before any of these
numbers are trusted, `run_canary()` scores a deliberately degraded configuration
and asserts the scores fall. An eval that cannot fail is not evidence.
"""
from __future__ import annotations

import math

import json
from pathlib import Path

from pydantic import BaseModel, Field

import re

from ..knowledge.graph import KnowledgeGraph, load_graph
from ..knowledge.retrieval import retrieve
from ..schemas import PatientDNA
from .citations import FACTUAL_MARKERS
from .prompt import PROMPT_VERSION, build_prompt
from .sampling import ContextOverflow
from .state_facts import is_state_id
from .structured import (
    StructuredAnswer,
    answer_schema,
    check_structured,
    has_inline_marker,
    parse_structured,
)

BATTERY_PATH = Path(__file__).resolve().parents[3] / "tests" / "eval" / "narration_battery.json"


_FIRST_PERSON = re.compile(r"\b(i|i'm|i've|i'd|my|mine|me|we|our|us)\b")


MustGroup = tuple[str, ...]


def expectations(case: dict) -> tuple[tuple[MustGroup, ...], tuple[str, ...]]:
    """The must-groups and may-set for one battery case, from either shape.

    A must entry may be a LIST, which is an **alternation**: a derivation chain
    gives "B-transport or its origin P-social_determinants.transport", and either
    one grounds the claim. Grading the alternation as a group is what makes that
    true of the metric rather than only of the author's intent — under a flat
    must-set, a model citing the origin instead of the barrier would be scored a
    miss for a citation the protocol calls correct.

    The pre-v3 shape (`expect_facts`, a flat list) reads as one single-member
    group each, so an archived battery still scores rather than needing a second
    code path. That shape was GENERATED from retrieval's top ranks, which is why
    the v3 protocol re-authors it: expectations taken from system output measure
    agreement with the system.
    """
    raw = case.get("expect")
    if raw is None:
        return tuple((fact_id,) for fact_id in case.get("expect_facts", [])), ()

    must: list[MustGroup] = []
    for entry in raw.get("must", []):
        if isinstance(entry, str):
            must.append((entry,))
        else:
            must.append(tuple(entry))
    return tuple(must), tuple(raw.get("may", []))


def is_circumstantial(text: str) -> bool:
    """Does this segment assert something about the SPEAKER'S OWN situation?

    The denominator of `state_coverage`, and the one fuzzy thing in this file.
    Three properties make the fuzziness safe here:

      * It is an OFFLINE EVAL, never a runtime gate — the same place the repo
        already permits claim-extraction heuristics.
      * It is **kind-independent** on purpose. Scoring only `factual` segments
        would make the metric blind to exactly the v2 pathology it exists to
        detect: a circumstantial claim relabelled `feeling` to dodge a citation
        would leave the denominator rather than fail the numerator, and the
        instrument would report health while the disease continued.
      * It errs toward INCLUDING, which grows the denominator and makes the bar
        harder rather than easier. "I worry about the side effects" scores as
        circumstantial though it is really a feeling. A metric that flatters
        itself under uncertainty would be the wrong error.

    First person plus concrete-world vocabulary, reusing the citation checker's
    own marker list so the two cannot drift apart.
    """
    lowered = (text or "").casefold()
    if not _FIRST_PERSON.search(lowered):
        return False
    return any(marker in lowered for marker in FACTUAL_MARKERS)


class CaseResult(BaseModel):
    case_id: str
    patient_id: str
    question: str
    cited: list[str] = Field(default_factory=list)
    # Flattened must-set, kept under the old name so archived readers still find
    # it. `expected_must` carries the alternation structure recall actually uses.
    expected_facts: list[str] = Field(default_factory=list)
    expected_must: list[list[str]] = Field(default_factory=list)
    expected_may: list[str] = Field(default_factory=list)
    retrieved_facts: list[str] = Field(default_factory=list)
    # The state ids this persona was OFFERED, so a state miss can be read as
    # "never had one to cite" rather than "declined to cite it".
    offered_state_ids: list[str] = Field(default_factory=list)
    citation_valid: bool = False
    factual_segments: int = 0
    total_segments: int = 0
    cited_factual_segments: int = 0
    # v3: the state-citation axis. `circumstantial_segments` is kind-independent
    # (see `is_circumstantial`), so a claim relabelled `feeling` still counts
    # against the denominator.
    circumstantial_segments: int = 0
    cited_circumstantial_segments: int = 0
    feeling_segments: int = 0
    inline_markers: int = 0
    # Rank positions (0-based) of the cited facts in the offered list — the
    # position-bias diagnostic.
    cited_positions: list[int] = Field(default_factory=list)
    attempts: int = 1
    grounded: bool = False
    parse_failed: bool = False
    response_chars: int = 0
    failure: str = ""
    # BOTH layers, archived per take. The bundle's reading protocol says read
    # the raw takes; metrics are not a read. And the v1 double-citation defect
    # was only visible in the RELATIONSHIP between the two — markers inside
    # `segments[].text` that the renderer then duplicated from `fact_ids` — so
    # archiving either one alone would have hidden it.
    fingerprint: str = ""
    segments: list[dict] = Field(default_factory=list)   # as the model emitted
    rendered: str = ""                                   # as a reader would see

    @property
    def question_tag(self) -> str:
        parts = self.case_id.split("-")
        return parts[1] if len(parts) > 2 else "unknown"


class ComplianceReport(BaseModel):
    """Scores for one (prompt, model, adapter) configuration."""

    label: str
    prompt_version: int
    model: str
    adapter_version: int
    n_cases: int

    citation_validity: float = 0.0
    factual_coverage: float = 0.0
    system_recall: float = 0.0
    model_recall: float = 0.0
    # v3. Pre-registered floor 0.6. Reported as 0.0 with no circumstantial
    # segments anywhere, which is itself a finding rather than a pass.
    state_coverage: float = 0.0
    # Diagnostic, no bar: what share of all citations are state ids. Reads the
    # over-correction arm — a jump here with flat controls is the new ids doing
    # their job; a jump everywhere is the model reaching for whatever is nearest.
    state_citation_share: float = 0.0
    # Pre-registered arm: model_recall over the F ids of questions whose must-set
    # names any. State ids are the easier citation path — a persona's
    # circumstances are always in context while graph facts must be retrieved and
    # judged relevant — so graph recall gets its own reading rather than being
    # averaged into a figure the new ids can carry on their own.
    f_recall: float = 0.0
    f_recall_cases: int = 0
    # f_recall over must-groups that NO state id can satisfy. The difference
    # between the two separates redirection from displacement: a mixed
    # alternation like ["P-medications.metformin", "F063"] is satisfied by either
    # id, so f_recall can fall while the claim stays perfectly grounded. Only a
    # fall in THIS figure means graph facts went uncited for claims that had no
    # other citation path.
    f_recall_exclusive: float = 0.0
    f_recall_exclusive_groups: int = 0
    # Pre-registered floor 0.1. A persona that never merely feels has been
    # schema'd out of personhood.
    feeling_fraction: float = 0.0
    # Pre-registered max 0. The v1 defect: markers written into spoken text.
    inline_marker_takes: int = 0
    retry_rate: float = 0.0
    hard_failure_rate: float = 0.0
    parse_failure_rate: float = 0.0
    # Pre-registered max 0, and until now the only bar `grade()` did not measure
    # — it passed a literal 0.0, so a HARD bar reported PASS in every run ever
    # recorded, including one where every prompt overflowed. Measured here, over
    # cases attempted rather than cases scored: an overflowed prompt never
    # reaches the model and leaves every other denominator.
    context_overflow_rate: float = 0.0

    # Diagnostics, deliberately without pass bars.
    position_histogram: dict[str, int] = Field(default_factory=dict)
    factual_fraction_by_tag: dict[str, float] = Field(default_factory=dict)
    # Degeneracy watch: no metric above catches a model that answers everything
    # with one short factual segment citing one correct fact. That scores
    # validity 1.0 and can clear recall on easy questions while being useless as
    # a persona voice. Only reading takes catches it; these support the eye.
    # How many circumstantial segments the whole run produced. state_coverage is
    # a ratio, and 0.0 from an empty denominator ("nobody said anything about
    # themselves") is a different fact from 0.0 from a failed numerator ("they
    # did and cited nothing"). Absence and failure are different truths.
    circumstantial_segments: int = 0
    mean_segments_per_take: float = 0.0
    mean_response_chars: float = 0.0
    single_segment_rate: float = 0.0

    results: list[CaseResult] = Field(default_factory=list)

    @property
    def relevance_agreement(self) -> float:
        """Back-compat alias for the end-to-end figure."""
        return self.system_recall

    @property
    def position_concentration(self) -> float:
        """Share of citations landing in the top two offered positions.

        Constrained decode plus a fact enum invites citing whatever appears
        first. High concentration is the signal to enable seeded fact-order
        permutation in the prompt builder.
        """
        total = sum(self.position_histogram.values())  # int-sum: ComplianceReport.position_histogram
        if not total:
            return 0.0
        top = sum(count for pos, count in self.position_histogram.items()  # int-sum: ComplianceReport.position_histogram
                  if int(pos) < 2)
        return round(top / total, 4)

    @property
    def overall(self) -> float:
        """Single number for comparing revisions. Not a quality claim.

        `relevance_agreement` is included deliberately. An earlier version of
        this composite averaged only validity, coverage and hard-failure — all of
        which a compliant model keeps at 1.0 no matter how bad its context is,
        because it simply cites whatever it was given. The canary caught it: the
        composite could not detect a starved context, which is the same
        "measuring stability, not relevance" failure that once affected the
        retrieval eval.

        `state_coverage` is deliberately NOT in it. This number is what the v0.1
        and v0.3 bundles are compared on, and a composite that changes its own
        definition between readings makes the comparison meaningless — the axis
        would look like a model improvement. The state lever is checked directly
        in `run_canary` instead.
        """
        return round(
            (self.citation_validity + self.factual_coverage
             + self.system_recall + (1.0 - self.hard_failure_rate)) / 4.0,
            4,
        )

    def headline(self) -> str:
        return (
            f"{self.label}: citation-validity {self.citation_validity:.0%}, "
            f"factual-coverage {self.factual_coverage:.0%}, "
            f"system-recall {self.system_recall:.0%}, "
            f"model-recall {self.model_recall:.0%}, "
            f"state-coverage {self.state_coverage:.0%}, "
            f"f-recall {self.f_recall:.0%}, "
            f"feeling {self.feeling_fraction:.0%}, "
            f"retries {self.retry_rate:.0%}, "
            f"hard failures {self.hard_failure_rate:.0%}"
        )


def load_battery(path: Path = BATTERY_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def score(
    cohort: list[PatientDNA],
    generate,
    graph: KnowledgeGraph | None = None,
    battery: list[dict] | None = None,
    label: str = "run",
    model: str = "unknown",
    degrade: str | None = None,
    on_take=None,
) -> ComplianceReport:
    """Run the battery and score it.

    `generate(prompt, schema, repair) -> str` returns a raw model response.
    Injected, so this scores the null backend, a cassette, or a live model
    identically.

    `degrade` is the canary lever — see `run_canary`. It is threaded through here
    rather than bolted on outside so the degraded run traverses exactly the same
    code path as a real one.

    `on_take(prompt, raw, check)` is called once per case with the FINAL attempt,
    so a caller that records cassettes records exactly the responses that were
    scored. It exists because the recorder used to run the battery a second time
    to capture its takes, which made the archived numbers describe a generation
    that no longer existed anywhere: same prompts, a second sample, and two of
    thirty takes drifted — enough to move `state_coverage` by five points. A
    report and a recording that disagree are worse than either alone, because
    each looks like evidence for the other. `raw` is "" and `check` is None when
    the prompt overflowed the context window and no call was made.
    """
    graph = graph if graph is not None else load_graph()
    battery = battery if battery is not None else load_battery()

    # Keyed by (condition, patient_id). patient_id is only unique WITHIN a
    # cohort — `synthetic-0000` exists in every condition — so keying on it alone
    # silently resolves every case to whichever condition was loaded last, and
    # the battery ends up scoring one condition's personas against another's
    # expected facts. Recall then measures nothing.
    by_key = {(dna.condition, dna.patient_id): dna for dna in cohort}

    results: list[CaseResult] = []
    overflowed: list[tuple[str, str]] = []
    for case in battery:
        key = (case.get("condition", ""), case.get("patient_id", ""))
        dna = by_key.get(key)
        if dna is None:
            raise KeyError(
                f"battery case {case['id']!r} names {key} which is not in the "
                "cohort; the battery and the cohort have diverged"
            )
        barriers = tuple(b.name for b in dna.barriers)
        retrieval = retrieve(
            graph, dna.condition, case["question"],
            limit=case.get("limit", 16), barriers=barriers,
        )

        if degrade == "truncate_context":
            # Starve the model of facts: coverage should collapse.
            retrieval = retrieval.model_copy(update={"facts": retrieval.facts[:1]})

        prompt = build_prompt(
            dna, retrieval, case["question"],
            # The v3 lever: rebuild the v2 configuration, graph ids only.
            include_state_facts=(degrade != "strip_state_ids"),
        )
        if degrade == "strip_instructions":
            stripped = prompt.system.split("CITATION RULES")[0]
            prompt = prompt.model_copy(update={"system": stripped})

        schema = answer_schema(prompt.allowed_fact_ids)
        if degrade == "unconstrained_ids":
            # Remove the enum, so fabricated ids become emittable again.
            schema["properties"]["segments"]["items"]["properties"]["fact_ids"] = {
                "type": "array", "items": {"type": "string"}
            }

        attempts = 0
        answer: StructuredAnswer | None = None
        check = None
        repair = None
        raw = ""
        try:
            while attempts < 2:
                attempts += 1
                raw = generate(prompt, schema, repair)
                answer = parse_structured(raw)
                if answer is None:
                    check = None
                    repair = "Return only a JSON object matching the schema."
                    continue
                check = check_structured(answer, prompt.allowed_fact_ids)
                if check.ok:
                    break
                from .structured import structured_repair_instruction

                repair = structured_repair_instruction(check)
        except ContextOverflow as exc:
            # A prompt that would not fit never reached the model, so it is not
            # evidence about the model. It leaves the behavioural denominators
            # entirely and is counted only in `context_overflow_rate` — which
            # `grade()` used to supply as a literal 0.0, making a pre-registered
            # HARD bar one that could not fail. Scoring it as a grounding failure
            # would be the opposite error: an instrument fault charged to the
            # model.
            overflowed.append((case["id"], str(exc)))
            if on_take is not None:
                on_take(prompt, "", None)
            continue

        if on_take is not None:
            on_take(prompt, raw, check)

        segments = answer.segments if answer else []
        factual = [s for s in segments if s.needs_citation]
        offered = [f.id for f in retrieval.facts]
        cited_ids = answer.cited_fact_ids if answer else []
        circumstantial = [s for s in segments if is_circumstantial(s.text)]
        must, may = expectations(case)
        results.append(CaseResult(
            case_id=case["id"],
            patient_id=dna.patient_id,
            question=case["question"],
            cited=cited_ids,
            expected_facts=[fact_id for group in must for fact_id in group],
            expected_must=[list(group) for group in must],
            expected_may=list(may),
            retrieved_facts=offered,
            citation_valid=bool(check and not check.unknown_citations),
            factual_segments=len(factual),
            total_segments=len(segments),
            cited_factual_segments=sum(1 for s in factual if s.fact_ids),
            offered_state_ids=sorted(prompt.allowed_state_ids),
            feeling_segments=len(segments) - len(factual),
            inline_markers=sum(
                1 for s in segments if has_inline_marker(s.text)
            ),
            circumstantial_segments=len(circumstantial),
            cited_circumstantial_segments=sum(
                1 for s in circumstantial
                if any(is_state_id(fact_id) for fact_id in s.fact_ids)
            ),
            cited_positions=[offered.index(c) for c in cited_ids if c in offered],
            attempts=attempts,
            grounded=bool(check and check.ok),
            parse_failed=answer is None,
            response_chars=len(answer.render()) if answer else 0,
            fingerprint=prompt.fingerprint,
            segments=[seg.model_dump() for seg in segments],
            rendered=answer.render() if answer else "",
            failure="" if (check and check.ok) else (
                check.summary if check else "unparseable response"
            ),
        ))

    n = len(results) or 1
    total_factual = sum(r.factual_segments for r in results)  # int-sum: CaseResult.factual_segments
    cited_factual = sum(r.cited_factual_segments for r in results)  # int-sum: CaseResult.cited_factual_segments

    # v3. Pooled over segments, not averaged over takes: a take with one
    # circumstantial segment would otherwise weigh as much as one with six.
    total_circumstantial = sum(r.circumstantial_segments for r in results)  # int-sum: CaseResult.circumstantial_segments
    cited_circumstantial = sum(r.cited_circumstantial_segments for r in results)  # int-sum: CaseResult.cited_circumstantial_segments
    total_segments = sum(r.total_segments for r in results)  # int-sum: CaseResult.total_segments
    feeling_total = sum(r.feeling_segments for r in results)  # int-sum: CaseResult.feeling_segments
    # RECALL, not precision. Precision (|cited & expected| / |cited|) stays at
    # 1.0 for a model that cites a single safe fact, so it cannot distinguish a
    # rich context from a starved one.
    #
    # SPLIT so a miss indicts the right component:
    #   system  — of all expected facts, how many were cited end to end
    #   model   — of the expected facts retrieval ACTUALLY OFFERED, how many
    #             were cited. System miss + model pass == retrieval problem.
    system_hits = system_total = 0
    model_hits = model_total = 0
    # Counted in the loop rather than summed over a comprehension: the operands
    # are list lengths and a predicate, neither of which can name a schema field
    # for `tests/test_float_accumulation.py` to check a marker against. Explicit
    # integer accumulation needs no marker to be exact.
    total_citations = state_citations = 0
    f_hits = f_total = f_cases = 0
    exclusive_hits = exclusive_total = 0
    positions: dict[str, int] = {}
    by_tag: dict[str, list[float]] = {}

    for result in results:
        cited = set(result.cited)
        # A group is satisfied by ANY of its members — see `expectations`.
        offered = set(result.retrieved_facts) | set(result.offered_state_ids)
        groups = [tuple(group) for group in result.expected_must]

        for fact_id in result.cited:
            total_citations += 1
            if is_state_id(fact_id):
                state_citations += 1

        if groups:
            system_total += len(groups)
            system_hits += sum(
                1 for group in groups if cited & set(group)
            )
            reachable = [g for g in groups if offered & set(g)]
            model_total += len(reachable)
            model_hits += sum(
                1 for group in reachable if cited & set(group)
            )

        # The F-only reading, over questions whose must-set names any F id.
        f_groups = [g for g in groups if any(not is_state_id(i) for i in g)]
        if f_groups:
            f_cases += 1
            for group in f_groups:
                f_ids = {i for i in group if not is_state_id(i)}
                if not (f_ids & offered):
                    continue
                f_total += 1
                if cited & f_ids:
                    f_hits += 1
                # Exclusive: no state id could have satisfied this group, so a
                # miss here is a graph fact genuinely left uncited.
                if len(f_ids) == len(group):
                    exclusive_total += 1
                    if cited & f_ids:
                        exclusive_hits += 1

        for position in result.cited_positions:
            key = str(position)
            positions[key] = positions.get(key, 0) + 1

        if result.total_segments:
            by_tag.setdefault(result.question_tag, []).append(
                result.factual_segments / result.total_segments
            )

    return ComplianceReport(
        label=label,
        prompt_version=PROMPT_VERSION,
        model=model,
        adapter_version=1,
        n_cases=len(results),
        citation_validity=round(sum(1 for r in results if r.citation_valid) / n, 4),
        factual_coverage=round(cited_factual / total_factual, 4) if total_factual else 1.0,
        system_recall=round(system_hits / system_total, 4) if system_total else 0.0,
        model_recall=round(model_hits / model_total, 4) if model_total else 0.0,
        state_coverage=(
            round(cited_circumstantial / total_circumstantial, 4)
            if total_circumstantial else 0.0
        ),
        circumstantial_segments=total_circumstantial,
        state_citation_share=(
            round(state_citations / total_citations, 4) if total_citations else 0.0
        ),
        f_recall=round(f_hits / f_total, 4) if f_total else 0.0,
        f_recall_cases=f_cases,
        f_recall_exclusive=(
            round(exclusive_hits / exclusive_total, 4) if exclusive_total else 0.0
        ),
        f_recall_exclusive_groups=exclusive_total,
        feeling_fraction=(
            round(feeling_total / total_segments, 4) if total_segments else 0.0
        ),
        inline_marker_takes=sum(1 for r in results if r.inline_markers),
        retry_rate=round(sum(1 for r in results if r.attempts > 1) / n, 4),
        hard_failure_rate=round(sum(1 for r in results if not r.grounded) / n, 4),
        parse_failure_rate=round(sum(1 for r in results if r.parse_failed) / n, 4),
        # Over cases ATTEMPTED, not cases scored. Dividing by `n` would shrink
        # the rate as more prompts overflowed, and reach 0/0 exactly when every
        # single one did.
        context_overflow_rate=round(
            len(overflowed) / (len(results) + len(overflowed)), 4
        ) if (results or overflowed) else 0.0,
        mean_segments_per_take=round(sum(r.total_segments for r in results) / n, 2),  # int-sum: CaseResult.total_segments
        mean_response_chars=round(sum(r.response_chars for r in results) / n, 1),  # int-sum: CaseResult.response_chars
        single_segment_rate=round(
            sum(1 for r in results if r.total_segments == 1) / n, 4
        ),
        position_histogram=dict(sorted(positions.items(), key=lambda kv: int(kv[0]))),
        factual_fraction_by_tag={
            tag: round(math.fsum(values) / len(values), 4)
            for tag, values in sorted(by_tag.items())
        },
        results=results,
    )


DEGRADATIONS = ("truncate_context", "strip_instructions", "unconstrained_ids",
                "strip_state_ids")

# Which score each lever is supposed to move. `overall` deliberately excludes
# state_coverage (see ComplianceReport.overall), so the state lever needs its own
# reading rather than a composite that would dilute it to invisibility.
LEVER_METRIC: dict[str, str] = {
    "truncate_context": "overall",
    "strip_instructions": "overall",
    "unconstrained_ids": "overall",
    "strip_state_ids": "state_coverage",
}


def run_canary(
    cohort: list[PatientDNA],
    generate,
    graph: KnowledgeGraph | None = None,
    battery: list[dict] | None = None,
    model: str = "unknown",
) -> dict:
    """Prove the eval can fail before trusting what it reports.

    Scores the healthy configuration and each deliberately broken one. If a
    degraded configuration does not score worse, the instrument is not measuring
    what it claims and its numbers mean nothing.
    """
    baseline = score(cohort, generate, graph=graph, battery=battery,
                     label="baseline", model=model)
    degraded = {
        lever: score(cohort, generate, graph=graph, battery=battery,
                     label=f"degraded:{lever}", model=model, degrade=lever)
        for lever in DEGRADATIONS
    }

    def moved(lever: str, report: ComplianceReport) -> bool:
        metric = LEVER_METRIC[lever]
        return getattr(report, metric) < getattr(baseline, metric)

    detected = {lever: moved(lever, report) for lever, report in degraded.items()}

    # The state lever must be CLEAN as well as effective: removing the P/B/J ids
    # should collapse state_coverage and leave graph recall roughly where it was.
    # Read on f_recall, as the pre-registration words it — this was implemented on
    # model_recall until 2026-08-23, which moves for a second reason entirely:
    # dropping the state ids makes state-only must-groups unreachable, shrinking
    # the denominator without any citation changing.
    #
    # MEASURED, and it fires: f_recall 0.5306 -> 0.6939 on qwen2.5:7b-instruct.
    # f_recall_exclusive — over must-groups no state id can satisfy — moves with
    # it, 0.4615 -> 0.6154, so this is not the benign reading where a mixed
    # alternation is simply grounded through its profile member instead of its
    # graph one. State ids DISPLACE graph citations for claims that have no other
    # citation path. That is a property of the v3 configuration, not a fault in
    # the lever, and it is what f_recall_holds_independently was registered to
    # catch. Reported, never silently reinterpreted.
    state_report = degraded["strip_state_ids"]
    lever_clean = abs(state_report.f_recall - baseline.f_recall) <= 0.1
    exclusive_drift = abs(
        state_report.f_recall_exclusive - baseline.f_recall_exclusive
    )

    # A lever cannot be shown to fire on an axis nothing exercised. With no
    # circumstantial segments anywhere, state_coverage is 0.0 on both sides for
    # want of a denominator, and calling that "the lever did not fire" would
    # blame the instrument for a battery that never asked the question.
    axis_exercised = baseline.circumstantial_segments > 0

    sensitive = detected["truncate_context"] and detected["strip_state_ids"]
    return {
        "baseline": baseline,
        "degraded": degraded,
        "detected": detected,
        "lever_metric": dict(LEVER_METRIC),
        "state_lever_clean": lever_clean,
        # How much of the f_recall movement survives when mixed alternations are
        # excluded. Near zero would mean redirection within a claim; anything
        # else is displacement between claims.
        "f_recall_exclusive_drift": round(exclusive_drift, 4),
        "state_axis_exercised": axis_exercised,
        # `unconstrained_ids` only bites a model that would actually fabricate an
        # id — the null backend never does — so it is reported, not required.
        # `strip_state_ids` IS required: v3 adds an axis, and an axis the
        # instrument cannot fail on is decoration. Pre-registered in
        # tests/eval/v3_expected_shape.json under canary_must_fire_first.
        "sensitive": sensitive,
        "verdict": _verdict(sensitive, detected, axis_exercised),
    }


def _verdict(sensitive: bool, detected: dict[str, bool], axis_exercised: bool) -> str:
    """One sentence naming what failed, in the order a reader should triage it.

    The grounding lever comes first because it is load-bearing: if truncating the
    facts does not move the score, nothing else in the report is evidence and the
    state axis is the least of it. Only once that fires is it worth separating
    "the battery never exercised the state axis" (a finding about the battery)
    from "the axis was exercised and the lever still did not move it" (a finding
    about the instrument).
    """
    if sensitive:
        return "eval detects degradation"
    if not detected["truncate_context"]:
        return "EVAL IS NOT SENSITIVE — its scores are not evidence"
    if not axis_exercised:
        return (
            "STATE AXIS NOT EXERCISED — no circumstantial segments to score, so "
            "state_coverage has no denominator and the lever cannot fire. This "
            "is a finding about the battery, not about the instrument."
        )
    return (
        "EVAL IS NOT SENSITIVE ON THE STATE AXIS — state_coverage did not fall "
        "when the P/B/J ids were removed, so a v3 state number would not be "
        "evidence"
    )


PASS_BARS_PATH = BATTERY_PATH.parent / "pass_bars.json"


class BarResult(BaseModel):
    metric: str
    kind: str
    bar: float
    observed: float
    passed: bool
    on_miss: str
    rationale: str


class Verdict(BaseModel):
    """Graded against bars registered BEFORE the first live run."""

    registered_on: str
    registered_before_first_live_run: bool
    bars: list[BarResult] = Field(default_factory=list)

    @property
    def hard_failures(self) -> list[BarResult]:
        return [b for b in self.bars if b.kind == "hard" and not b.passed]

    @property
    def soft_failures(self) -> list[BarResult]:
        return [b for b in self.bars if b.kind == "soft" and not b.passed]

    @property
    def passed(self) -> bool:
        return not self.hard_failures and not self.soft_failures

    def next_action(self) -> str:
        """What a miss actually indicts — the point of splitting the metrics."""
        if self.hard_failures:
            return (
                "HARD BAR MISSED: "
                + "; ".join(f"{b.metric} ({b.on_miss})" for b in self.hard_failures)
                + ". Fix the plumbing before drawing any conclusion about the model."
            )
        if not self.soft_failures:
            return "all bars met"

        missed = {b.metric for b in self.soft_failures}
        # System recall can miss because retrieval never surfaced the fact. If
        # the model cleared its own bar, the prompt is not the problem.
        if "system_recall" in missed and "model_recall" not in missed:
            return (
                "system_recall missed while model_recall passed: retrieval did not "
                "surface the expected facts. Iterate the intent scorer in "
                "knowledge/retrieval.py, NOT the prompt."
            )
        return (
            "soft bars missed: " + ", ".join(sorted(missed))
            + ". Iterate the prompt, then re-run the battery."
        )


def grade(report: ComplianceReport, path: Path = PASS_BARS_PATH) -> Verdict:
    """Grade a report against the pre-registered bars. No bar is chosen here."""
    config = json.loads(path.read_text(encoding="utf-8"))
    observed = {
        "citation_validity": report.citation_validity,
        "parse_failure_rate": report.parse_failure_rate,
        "context_overflow_rate": report.context_overflow_rate,
        "factual_coverage": report.factual_coverage,
        "model_recall": report.model_recall,
        "system_recall": report.system_recall,
        "hard_failure_rate": report.hard_failure_rate,
        "retry_rate": report.retry_rate,
    }

    bars: list[BarResult] = []
    for kind in ("hard", "soft"):
        for metric, spec in config.get(kind, {}).items():
            if metric not in observed:
                continue
            value = observed[metric]
            if "min" in spec:
                bar, passed = spec["min"], value >= spec["min"]
            else:
                bar, passed = spec["max"], value <= spec["max"]
            bars.append(BarResult(
                metric=metric, kind=kind, bar=bar, observed=value,
                passed=passed, on_miss=spec.get("on_miss", ""),
                rationale=spec.get("rationale", ""),
            ))

    return Verdict(
        registered_on=config["registered_on"],
        registered_before_first_live_run=config["registered_before_first_live_run"],
        bars=bars,
    )
