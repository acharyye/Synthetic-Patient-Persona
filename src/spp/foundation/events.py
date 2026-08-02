"""Event-sourced persona state.

A persona is an initial profile plus an append-only event log. Current state is a
`fold` over that log — never stored, always derived. That buys four things the
roadmap depends on:

  * **Replay** — re-run a simulation and diff the event streams, not the summaries.
  * **Time travel** — `fold(log, until=t)` gives the state at any point.
  * **Counterfactual forking** — `log.fork_at(t)` branches a completed run, and
    because seeds are named (see `rng.py`) the divergence isolates the design
    change from noise. This is the "wind tunnel" mechanic.
  * **Audit** — every state change has a cause, a timestamp and a seed on record.

The invariant that makes all of it work: **the fold is pure.** No I/O, no clock,
no global RNG. Same log in, same state out, byte for byte.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Iterator

from pydantic import BaseModel, Field, model_validator

# Bump when the meaning of an event type or payload changes. Stamped into every
# log so a replay — especially a Phase 2 counterfactual fork of a log written by
# an older build — can refuse to run rather than silently misread it.
SCHEMA_VERSION = 1


class IncompatibleEventLog(ValueError):
    """A persisted log's schema version is not one this build can fold."""


class EventType(str, Enum):
    """What can happen to a persona. Extend deliberately — every new type needs
    a corresponding case in `fold`, and the golden tests will catch omissions.
    """

    SCREENED = "screened"
    SCREEN_FAILED = "screen_failed"
    ENROLLED = "enrolled"
    VISIT_COMPLETED = "visit_completed"
    VISIT_MISSED = "visit_missed"
    BURDEN_ACCRUED = "burden_accrued"
    BARRIER_TRIGGERED = "barrier_triggered"
    INTERVIEWED = "interviewed"
    DROPPED_OUT = "dropped_out"
    COMPLETED = "completed"


class JourneyStage(str, Enum):
    """Guarded state machine: unaware -> screened -> active -> terminal."""

    UNAWARE = "unaware"
    SCREENED = "screened"
    ACTIVE = "active"
    DROPPED = "dropped"
    COMPLETED = "completed"


# Terminal stages absorb: once here, no event may move the persona out.
TERMINAL_STAGES = frozenset({JourneyStage.DROPPED, JourneyStage.COMPLETED})


class PersonaEvent(BaseModel):
    """One thing that happened. Immutable once appended."""

    model_config = {"frozen": True}

    seq: int = Field(ge=0, description="position in the log, 0-based")
    persona_id: str
    type: EventType
    t: int = Field(ge=0, description="simulation time, in days from enrolment")
    payload: dict[str, Any] = Field(default_factory=dict)
    seed_path: str | None = Field(
        default=None, description="SeedScope.path of the draw that produced this"
    )

    def summary(self) -> str:
        detail = ", ".join(f"{k}={v}" for k, v in sorted(self.payload.items()))
        return f"t+{self.t:>4}d  {self.type.value}" + (f"  ({detail})" if detail else "")


class BurdenVector(BaseModel):
    """Burden as a structured vector, not a scalar (roadmap 3.3).

    The total is kept for ranking; the components are what let a report say
    *which* kind of burden broke this persona, which a single number cannot.
    """

    time: float = 0.0
    travel: float = 0.0
    procedural: float = 0.0
    cognitive: float = 0.0
    financial: float = 0.0
    scheduling: float = 0.0

    @property
    def total(self) -> float:
        return round(
            self.time + self.travel + self.procedural
            + self.cognitive + self.financial + self.scheduling,
            4,
        )

    def plus(self, other: BurdenVector) -> BurdenVector:
        return BurdenVector(
            **{
                field: getattr(self, field) + getattr(other, field)
                for field in type(self).model_fields
            }
        )

    def dominant(self) -> str | None:
        """The component carrying the most weight — the headline for a report."""
        components = {f: getattr(self, f) for f in type(self).model_fields}
        top = max(components, key=lambda k: components[k])
        return top if components[top] > 0 else None


class PersonaState(BaseModel):
    """The fold result. Derived, never persisted as source of truth."""

    persona_id: str
    stage: JourneyStage = JourneyStage.UNAWARE
    t: int = 0
    eligible: bool | None = None
    visits_completed: int = 0
    visits_missed: int = 0
    burden: BurdenVector = Field(default_factory=BurdenVector)
    barriers: list[str] = Field(default_factory=list)
    interviews: int = 0
    exit_reason: str | None = None
    event_count: int = 0

    @property
    def active(self) -> bool:
        return self.stage == JourneyStage.ACTIVE

    @property
    def terminal(self) -> bool:
        return self.stage in TERMINAL_STAGES

    @property
    def attendance_rate(self) -> float | None:
        scheduled = self.visits_completed + self.visits_missed
        return round(self.visits_completed / scheduled, 3) if scheduled else None


class EventLog(BaseModel):
    """Append-only log for one persona."""

    model_config = {"validate_assignment": True}

    persona_id: str
    schema_version: int = SCHEMA_VERSION
    events: list[PersonaEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_ordering(self) -> EventLog:
        for i, event in enumerate(self.events):
            if event.seq != i:
                raise ValueError(f"event {i} has seq {event.seq}; log must be dense")
            if event.persona_id != self.persona_id:
                raise ValueError(
                    f"event {i} belongs to {event.persona_id!r}, not {self.persona_id!r}"
                )
        times = [e.t for e in self.events]
        if times != sorted(times):
            raise ValueError("events must be in non-decreasing time order")
        return self

    def __len__(self) -> int:
        return len(self.events)

    def __iter__(self) -> Iterator[PersonaEvent]:  # type: ignore[override]
        return iter(self.events)

    def append(
        self,
        type: EventType,
        t: int,
        payload: dict[str, Any] | None = None,
        seed_path: str | None = None,
    ) -> PersonaEvent:
        """Append one event. Rejects time going backwards — a log that can be
        written out of order is a log you cannot trust a fold over.
        """
        if self.events and t < self.events[-1].t:
            raise ValueError(
                f"cannot append at t={t}; log is already at t={self.events[-1].t}"
            )
        event = PersonaEvent(
            seq=len(self.events),
            persona_id=self.persona_id,
            type=type,
            t=t,
            payload=payload or {},
            seed_path=seed_path,
        )
        self.events = [*self.events, event]
        return event

    def fork_at(self, t: int) -> EventLog:
        """Branch a copy retaining only events up to and including `t`.

        The counterfactual primitive: fork, apply a changed scenario, replay with
        the same named seeds, diff the outcomes.
        """
        return EventLog(
            persona_id=self.persona_id,
            schema_version=self.schema_version,
            events=[e for e in self.events if e.t <= t],
        )

    def of_type(self, type: EventType) -> list[PersonaEvent]:
        return [e for e in self.events if e.type == type]

    def require_compatible(self) -> EventLog:
        """Raise unless this log's schema is one this build understands.

        Called on every load. A fork-and-replay against a log written by a
        different event schema must fail loudly — silently misreading a payload
        would produce a counterfactual diff that looks valid and isn't.
        """
        if self.schema_version != SCHEMA_VERSION:
            raise IncompatibleEventLog(
                f"log for {self.persona_id!r} has event schema v{self.schema_version}, "
                f"this build folds v{SCHEMA_VERSION}. Migrate it before replaying."
            )
        return self

    def to_rows(self) -> list[dict]:
        """Flatten to tabular rows for columnar storage.

        Payloads are JSON-encoded rather than exploded into columns: they are
        heterogeneous by event type, and a sparse wide table would make the
        schema depend on which events happened to occur in a given run.
        """
        import json

        return [
            {
                "persona_id": self.persona_id,
                "schema_version": self.schema_version,
                "seq": event.seq,
                "type": event.type.value,
                "t": event.t,
                "payload": json.dumps(event.payload, sort_keys=True),
                "seed_path": event.seed_path,
            }
            for event in self.events
        ]

    @classmethod
    def from_rows(cls, rows: list[dict]) -> EventLog:
        """Rebuild a log from `to_rows` output, validating the schema version."""
        import json
        import math

        if not rows:
            raise ValueError("cannot rebuild an EventLog from no rows")

        def optional_str(value: object) -> str | None:
            """Columnar round-trips turn a missing string into NaN, not None, and
            NaN is truthy — so `value or None` would smuggle a float through.
            """
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return None
            text = str(value)
            return text or None

        ordered = sorted(rows, key=lambda row: row["seq"])
        log = cls(
            persona_id=str(ordered[0]["persona_id"]),
            schema_version=int(ordered[0]["schema_version"]),
            events=[
                PersonaEvent(
                    seq=int(row["seq"]),
                    persona_id=str(row["persona_id"]),
                    type=EventType(row["type"]),
                    t=int(row["t"]),
                    payload=json.loads(payload) if (payload := optional_str(
                        row.get("payload"))) else {},
                    seed_path=optional_str(row.get("seed_path")),
                )
                for row in ordered
            ],
        )
        return log.require_compatible()

    def transcript(self) -> str:
        return "\n".join(e.summary() for e in self.events)


def fold(log: EventLog, until: int | None = None) -> PersonaState:
    """Derive current state from the log. Pure: no I/O, no clock, no RNG.

    Unknown event types are ignored rather than raising, so an old log written by
    a newer build still folds — but `event_count` still counts them, which is how
    you notice.
    """
    state = PersonaState(persona_id=log.persona_id)

    for event in log.events:
        if until is not None and event.t > until:
            break

        state.event_count += 1
        state.t = event.t

        # Terminal stages absorb: a dropped persona cannot complete a visit.
        if state.stage in TERMINAL_STAGES:
            continue

        match event.type:
            case EventType.SCREENED:
                state.stage = JourneyStage.SCREENED
                state.eligible = bool(event.payload.get("eligible", True))
            case EventType.SCREEN_FAILED:
                state.stage = JourneyStage.DROPPED
                state.eligible = False
                state.exit_reason = event.payload.get("reason", "screen failure")
            case EventType.ENROLLED:
                state.stage = JourneyStage.ACTIVE
                state.eligible = True
            case EventType.VISIT_COMPLETED:
                state.visits_completed += 1
            case EventType.VISIT_MISSED:
                state.visits_missed += 1
            case EventType.BURDEN_ACCRUED:
                state.burden = state.burden.plus(
                    BurdenVector(**event.payload.get("burden", {}))
                )
            case EventType.BARRIER_TRIGGERED:
                barrier = event.payload.get("barrier")
                if barrier and barrier not in state.barriers:
                    state.barriers.append(barrier)
            case EventType.INTERVIEWED:
                state.interviews += 1
            case EventType.DROPPED_OUT:
                state.stage = JourneyStage.DROPPED
                state.exit_reason = event.payload.get("reason", "dropped out")
            case EventType.COMPLETED:
                state.stage = JourneyStage.COMPLETED
                state.exit_reason = None

    return state
