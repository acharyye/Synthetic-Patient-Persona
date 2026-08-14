"""Evaluate draft trial inclusion/exclusion criteria against Patient DNA.

This answers the design question "who would this protocol screen out, and which
criterion is doing the damage" — it is a design/ideation aid, NOT a regulatory
eligibility determination and not a screening decision for any real person.

GRAMMAR — one clause per string, no boolean operators inside a clause:

    comparison    age >= 50
                  adherence_baseline < 0.5
                  biomarkers.HbA1c_pct > 7.5
                  sdoh.transport != none
                  n_comorbidities <= 2
    membership    stage in {moderate, advanced}
                  sex not in {male}
    presence      CKD                     (has it, anywhere clinical)
                  not metformin           (is not on it)

Inclusion criteria are ANDed. Exclusion criteria are ORed — any hit excludes.

Two deliberate design decisions:

  * An unparseable clause or unknown field raises `CriterionError` at parse time,
    before any patient is evaluated. A typo in a protocol must fail loudly, never
    quietly screen out a cohort.
  * A clause over a field the patient has no value for evaluates False. So an
    inclusion criterion on a missing biomarker fails the patient (you cannot
    confirm they qualify) while an exclusion criterion on it does not exclude
    them (you cannot confirm they should be). Conservative in both directions.
"""
from __future__ import annotations

import math

import operator
import re
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from ..schemas import PatientDNA


class CriterionError(ValueError):
    """A criterion string could not be parsed, or names a field we don't have."""


# ---------------------------------------------------------------------------
# Field resolution
# ---------------------------------------------------------------------------

# Scalars readable straight off PatientDNA.
_SCALAR_FIELDS = {
    "age",
    "sex",
    "ancestry",
    "condition",
    "stage",
    "adherence_baseline",
    "health_literacy",
}

# Derived scalars — cheap aggregates protocol writers reach for constantly.
_DERIVED_FIELDS: dict[str, Callable[[PatientDNA], Any]] = {
    "n_comorbidities": lambda d: len(d.comorbidities),
    "n_medications": lambda d: len(d.medications),
    "mean_medication_adherence": lambda d: (
        round(math.fsum(m.adherence for m in d.medications) / len(d.medications), 3)
        if d.medications
        else None
    ),
}

# Namespaced dict lookups: `biomarkers.HbA1c_pct`, `sdoh.transport`,
# `traits.mobility`.
#
# NOTE ON EVALUATION CONTEXT — one parser, two consumers:
#   * eligibility evaluates at SCREENING time against a complete profile;
#   * barrier derivation (cohort/traits.py) evaluates at GENERATION time against
#     a profile still being built.
# Same grammar, different guarantees about what is populated. See the migration
# test in tests/test_derivation_parity.py.
_NAMESPACES: dict[str, Callable[[PatientDNA], dict[str, Any]]] = {
    "biomarkers": lambda d: d.biomarkers,
    "sdoh": lambda d: d.social_determinants,
    "social_determinants": lambda d: d.social_determinants,
    "traits": lambda d: d.traits,
}

# Ordered ladders that make ordering comparisons meaningful on string fields.
# Both operands must live in the same ladder or the comparison is rejected.
_ORDINAL_LADDERS: list[list[str]] = [
    ["low", "medium", "high"],
    ["early", "moderate", "advanced"],
    ["gold1", "gold2", "gold3", "gold4"],
    ["nyha1", "nyha2", "nyha3", "nyha4"],
    ["i", "ii", "iii", "iv"],
]

_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "=": operator.eq,
    "!=": operator.ne,
}
_EQUALITY_OPS = {"==", "=", "!="}

_MISSING = object()


def known_fields() -> list[str]:
    """Everything a criterion may reference — surfaced in error messages."""
    return sorted(
        _SCALAR_FIELDS
        | set(_DERIVED_FIELDS)
        | {f"{ns}.<key>" for ns in ("biomarkers", "sdoh", "traits")}
    )


def _validate_field(field: str) -> None:
    if "." in field:
        namespace = field.split(".", 1)[0]
        if namespace not in _NAMESPACES:
            raise CriterionError(
                f"unknown field namespace {namespace!r}; expected one of "
                f"{sorted(_NAMESPACES)}"
            )
        return
    if field not in _SCALAR_FIELDS and field not in _DERIVED_FIELDS:
        raise CriterionError(
            f"unknown field {field!r}. Known fields: {', '.join(known_fields())}"
        )


def _resolve(dna: PatientDNA, field: str) -> Any:
    """Return the patient's value for `field`, or `_MISSING` if not recorded."""
    if "." in field:
        namespace, key = field.split(".", 1)
        source = _NAMESPACES[namespace](dna)
        for existing, value in source.items():
            if existing.casefold() == key.casefold():
                return value
        return _MISSING
    if field in _DERIVED_FIELDS:
        value = _DERIVED_FIELDS[field](dna)
    else:
        value = getattr(dna, field)
    return _MISSING if value is None else value


def _coerce(raw: str) -> float | str:
    text = raw.strip().strip("'\"")
    try:
        return float(text)
    except ValueError:
        return text


def _ordinal_pair(left: str, right: str) -> tuple[int, int] | None:
    lo, ro = left.casefold(), right.casefold()
    for ladder in _ORDINAL_LADDERS:
        if lo in ladder and ro in ladder:
            return ladder.index(lo), ladder.index(ro)
    return None


# ---------------------------------------------------------------------------
# Criteria
# ---------------------------------------------------------------------------


class Criterion:
    """A single parsed clause. `matches` means 'this clause is true of them'."""

    text: str

    def matches(self, dna: PatientDNA) -> tuple[bool, str]:
        raise NotImplementedError


class Comparison(Criterion):
    def __init__(self, text: str, field: str, op: str, value: float | str) -> None:
        _validate_field(field)
        self.text, self.field, self.op, self.value = text, field, op, value

    def matches(self, dna: PatientDNA) -> tuple[bool, str]:
        actual = _resolve(dna, self.field)
        if actual is _MISSING:
            return False, f"{self.field} not recorded"

        if isinstance(self.value, float):
            try:
                return _OPS[self.op](float(actual), self.value), f"{self.field}={actual}"
            except (TypeError, ValueError):
                raise CriterionError(
                    f"{self.field!r} is {actual!r}, which cannot be compared "
                    f"numerically against {self.value}"
                ) from None

        actual_text = str(actual)
        if self.op in _EQUALITY_OPS:
            equal = actual_text.casefold() == str(self.value).casefold()
            result = equal if self.op != "!=" else not equal
            return result, f"{self.field}={actual_text}"

        ranks = _ordinal_pair(actual_text, str(self.value))
        if ranks is None:
            raise CriterionError(
                f"cannot order {self.field!r} ({actual_text!r}) against "
                f"{self.value!r} — no shared ordinal scale. Use == / != / in {{}}."
            )
        return _OPS[self.op](*ranks), f"{self.field}={actual_text}"


class Membership(Criterion):
    def __init__(self, text: str, field: str, values: list[str], negated: bool) -> None:
        _validate_field(field)
        if not values:
            raise CriterionError(f"empty value set in {text!r}")
        self.text, self.field, self.negated = text, field, negated
        self.values = [v.casefold() for v in values]

    def matches(self, dna: PatientDNA) -> tuple[bool, str]:
        actual = _resolve(dna, self.field)
        if actual is _MISSING:
            return False, f"{self.field} not recorded"
        inside = str(actual).casefold() in self.values
        return (not inside if self.negated else inside), f"{self.field}={actual}"


class Presence(Criterion):
    """Bare clinical term: does this patient have it / take it?

    Looks across the primary condition, comorbidities and medication names.
    Matching is exact on normalised text, then falls back to containment so
    `diabetes` finds `type 2 diabetes`.
    """

    def __init__(self, text: str, term: str, negated: bool) -> None:
        self.text, self.term, self.negated = text, term.strip().casefold(), negated
        if not self.term:
            raise CriterionError(f"empty term in {text!r}")

    def matches(self, dna: PatientDNA) -> tuple[bool, str]:
        haystack = [dna.condition, *dna.comorbidities, *(m.name for m in dna.medications)]
        normalised = [h.casefold() for h in haystack if h]
        hit = next(
            (h for h in normalised if h == self.term),
            next((h for h in normalised if self.term in h or h in self.term), None),
        )
        found = hit is not None
        detail = f"has {hit}" if found else f"no record of {self.term}"
        return (not found if self.negated else found), detail


_MEMBER_RE = re.compile(
    r"^(?P<field>[A-Za-z_][\w.]*)\s+(?P<neg>not\s+)?in\s*\{(?P<values>[^}]*)\}$",
    re.IGNORECASE,
)
# The value must not start with an operator character, otherwise `age >= ` would
# backtrack into op `>` with the literal value `=` instead of failing to parse.
_COMPARE_RE = re.compile(
    r"^(?P<field>[A-Za-z_][\w.]*)\s*(?P<op><=|>=|!=|==|=|<|>)\s*(?P<value>[^<>=!\s].*)$"
)
_PRESENCE_RE = re.compile(
    r"^(?P<neg>not\s+)?(?P<term>[A-Za-z0-9][\w \-/'()]*)$", re.IGNORECASE
)


def parse_criterion(text: str) -> Criterion:
    """Parse one clause. Raises CriterionError on anything it can't read."""
    raw = (text or "").strip()
    if not raw:
        raise CriterionError("empty criterion")

    if match := _MEMBER_RE.match(raw):
        values = [v.strip().strip("'\"") for v in match["values"].split(",") if v.strip()]
        return Membership(raw, match["field"], values, negated=bool(match["neg"]))

    if match := _COMPARE_RE.match(raw):
        return Comparison(raw, match["field"], match["op"], _coerce(match["value"]))

    if match := _PRESENCE_RE.match(raw):
        return Presence(raw, match["term"], negated=bool(match["neg"]))

    raise CriterionError(
        f"could not parse criterion {raw!r}. Expected 'field op value', "
        "'field in {a, b}', or a bare clinical term."
    )


def parse_criteria(texts: list[str]) -> list[Criterion]:
    return [parse_criterion(t) for t in texts]


# ---------------------------------------------------------------------------
# Screening
# ---------------------------------------------------------------------------


class PatientVerdict(BaseModel):
    patient_id: str
    eligible: bool
    failed_inclusion: list[str] = Field(default_factory=list)
    matched_exclusion: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class CriterionImpact(BaseModel):
    """How much attrition one criterion causes, on its own and uniquely."""

    criterion: str
    kind: Literal["inclusion", "exclusion"]
    screened_out: int
    screened_out_rate: float
    # Patients who would have been eligible were it not for this one criterion.
    # The number that tells you which line of the protocol to renegotiate.
    sole_reason: int


class ScreeningResult(BaseModel):
    n_screened: int
    n_eligible: int
    eligibility_rate: float
    verdicts: list[PatientVerdict]
    criteria_impact: list[CriterionImpact]

    @property
    def eligible_ids(self) -> list[str]:
        return [v.patient_id for v in self.verdicts if v.eligible]


def screen(
    cohort: list[PatientDNA],
    inclusion: list[str] | None = None,
    exclusion: list[str] | None = None,
) -> ScreeningResult:
    """Apply criteria to a cohort and report attrition, per patient and per rule.

    Criteria are parsed up front so a malformed protocol raises before any
    patient is scored.
    """
    inclusion_criteria = parse_criteria(inclusion or [])
    exclusion_criteria = parse_criteria(exclusion or [])

    verdicts: list[PatientVerdict] = []
    # criterion text -> patient ids it screened out
    blocked_by: dict[str, list[str]] = {
        c.text: [] for c in (*inclusion_criteria, *exclusion_criteria)
    }

    for dna in cohort:
        failed_inclusion: list[str] = []
        matched_exclusion: list[str] = []
        reasons: list[str] = []

        for criterion in inclusion_criteria:
            ok, detail = criterion.matches(dna)
            if not ok:
                failed_inclusion.append(criterion.text)
                blocked_by[criterion.text].append(dna.patient_id)
                reasons.append(f"fails inclusion '{criterion.text}' ({detail})")

        for criterion in exclusion_criteria:
            hit, detail = criterion.matches(dna)
            if hit:
                matched_exclusion.append(criterion.text)
                blocked_by[criterion.text].append(dna.patient_id)
                reasons.append(f"meets exclusion '{criterion.text}' ({detail})")

        verdicts.append(
            PatientVerdict(
                patient_id=dna.patient_id,
                eligible=not failed_inclusion and not matched_exclusion,
                failed_inclusion=failed_inclusion,
                matched_exclusion=matched_exclusion,
                reasons=reasons,
            )
        )

    n = len(cohort)
    blockers_per_patient = {
        v.patient_id: len(v.failed_inclusion) + len(v.matched_exclusion) for v in verdicts
    }

    impact = [
        CriterionImpact(
            criterion=criterion.text,
            kind=kind,
            screened_out=len(blocked_by[criterion.text]),
            screened_out_rate=round(len(blocked_by[criterion.text]) / n, 3) if n else 0.0,
            sole_reason=sum(
                1 for pid in blocked_by[criterion.text] if blockers_per_patient[pid] == 1
            ),
        )
        for kind, criteria in (
            ("inclusion", inclusion_criteria),
            ("exclusion", exclusion_criteria),
        )
        for criterion in criteria
    ]
    impact.sort(key=lambda c: (-c.screened_out, -c.sole_reason))

    n_eligible = sum(1 for v in verdicts if v.eligible)
    return ScreeningResult(
        n_screened=n,
        n_eligible=n_eligible,
        eligibility_rate=round(n_eligible / n, 3) if n else 0.0,
        verdicts=verdicts,
        criteria_impact=impact,
    )
