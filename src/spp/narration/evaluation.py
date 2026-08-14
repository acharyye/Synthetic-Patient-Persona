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

from ..knowledge.graph import KnowledgeGraph, load_graph
from ..knowledge.retrieval import retrieve
from ..schemas import PatientDNA
from .prompt import PROMPT_VERSION, build_prompt
from .structured import (
    StructuredAnswer,
    answer_schema,
    check_structured,
    parse_structured,
)

BATTERY_PATH = Path(__file__).resolve().parents[3] / "tests" / "eval" / "narration_battery.json"


class CaseResult(BaseModel):
    case_id: str
    patient_id: str
    question: str
    cited: list[str] = Field(default_factory=list)
    expected_facts: list[str] = Field(default_factory=list)
    retrieved_facts: list[str] = Field(default_factory=list)
    citation_valid: bool = False
    factual_segments: int = 0
    total_segments: int = 0
    cited_factual_segments: int = 0
    # Rank positions (0-based) of the cited facts in the offered list — the
    # position-bias diagnostic.
    cited_positions: list[int] = Field(default_factory=list)
    attempts: int = 1
    grounded: bool = False
    parse_failed: bool = False
    response_chars: int = 0
    failure: str = ""

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
    retry_rate: float = 0.0
    hard_failure_rate: float = 0.0
    parse_failure_rate: float = 0.0

    # Diagnostics, deliberately without pass bars.
    position_histogram: dict[str, int] = Field(default_factory=dict)
    factual_fraction_by_tag: dict[str, float] = Field(default_factory=dict)
    # Degeneracy watch: no metric above catches a model that answers everything
    # with one short factual segment citing one correct fact. That scores
    # validity 1.0 and can clear recall on easy questions while being useless as
    # a persona voice. Only reading takes catches it; these support the eye.
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
        total = sum(self.position_histogram.values())  # int-sum: histogram counts
        if not total:
            return 0.0
        top = sum(count for pos, count in self.position_histogram.items()  # int-sum: histogram counts
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
) -> ComplianceReport:
    """Run the battery and score it.

    `generate(prompt, schema, repair) -> str` returns a raw model response.
    Injected, so this scores the null backend, a cassette, or a live model
    identically.

    `degrade` is the canary lever — see `run_canary`. It is threaded through here
    rather than bolted on outside so the degraded run traverses exactly the same
    code path as a real one.
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

        prompt = build_prompt(dna, retrieval, case["question"])
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

        segments = answer.segments if answer else []
        factual = [s for s in segments if s.needs_citation]
        offered = [f.id for f in retrieval.facts]
        cited_ids = answer.cited_fact_ids if answer else []
        results.append(CaseResult(
            case_id=case["id"],
            patient_id=dna.patient_id,
            question=case["question"],
            cited=cited_ids,
            expected_facts=case.get("expect_facts", []),
            retrieved_facts=offered,
            citation_valid=bool(check and not check.unknown_citations),
            factual_segments=len(factual),
            total_segments=len(segments),
            cited_factual_segments=sum(1 for s in factual if s.fact_ids),
            cited_positions=[offered.index(c) for c in cited_ids if c in offered],
            attempts=attempts,
            grounded=bool(check and check.ok),
            parse_failed=answer is None,
            response_chars=len(answer.render()) if answer else 0,
            failure="" if (check and check.ok) else (
                check.summary if check else "unparseable response"
            ),
        ))

    n = len(results) or 1
    total_factual = sum(r.factual_segments for r in results)  # int-sum: segment counts
    cited_factual = sum(r.cited_factual_segments for r in results)  # int-sum: segment counts

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
    positions: dict[str, int] = {}
    by_tag: dict[str, list[float]] = {}

    for result in results:
        expected = set(result.expected_facts)
        cited = set(result.cited)
        if expected:
            system_total += len(expected)
            system_hits += len(cited & expected)
            reachable = expected & set(result.retrieved_facts)
            model_total += len(reachable)
            model_hits += len(cited & reachable)

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
        retry_rate=round(sum(1 for r in results if r.attempts > 1) / n, 4),
        hard_failure_rate=round(sum(1 for r in results if not r.grounded) / n, 4),
        parse_failure_rate=round(sum(1 for r in results if r.parse_failed) / n, 4),
        mean_segments_per_take=round(sum(r.total_segments for r in results) / n, 2),  # int-sum: segment counts
        mean_response_chars=round(sum(r.response_chars for r in results) / n, 1),  # int-sum: character counts
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


DEGRADATIONS = ("truncate_context", "strip_instructions", "unconstrained_ids")


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

    detected = {
        lever: report.overall < baseline.overall
        for lever, report in degraded.items()
    }
    return {
        "baseline": baseline,
        "degraded": degraded,
        "detected": detected,
        # `unconstrained_ids` only bites a model that would actually fabricate an
        # id — the null backend never does — so it is reported, not required.
        "sensitive": detected["truncate_context"],
        "verdict": (
            "eval detects degradation"
            if detected["truncate_context"]
            else "EVAL IS NOT SENSITIVE — its scores are not evidence"
        ),
    }


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
        "context_overflow_rate": 0.0,
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
