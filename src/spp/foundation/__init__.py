"""Foundation layer — everything else is built on this.

Four guarantees live here, and the rest of the system depends on all of them:
  rng.py         reproducibility (named seed hierarchy)
  events.py      auditability and counterfactuals (event sourcing)
  ledger.py      explainability (no magic numbers in simulation code)
  versioning.py  durability (old cohorts still load)
  llm.py         offline-first (null backend keeps workflows running)
"""
from .events import (
    BurdenVector,
    EventLog,
    EventType,
    JourneyStage,
    PersonaEvent,
    PersonaState,
    fold,
)
from .ledger import (
    LEDGER,
    LEDGER_SCHEMA_VERSION,
    Assumption,
    AssumptionLedger,
    Confidence,
    register,
)
from .llm import LLMResult, generate, generate_structured, get_backend
from .rng import SeedScope, cohort_scope, derive_seed, event_scope, persona_scope
from .versioning import MigrationError, current_version, migrate, migration, register_schema

__all__ = [
    "LEDGER",
    "LEDGER_SCHEMA_VERSION",
    "Assumption",
    "AssumptionLedger",
    "BurdenVector",
    "Confidence",
    "EventLog",
    "EventType",
    "JourneyStage",
    "LLMResult",
    "MigrationError",
    "PersonaEvent",
    "PersonaState",
    "SeedScope",
    "cohort_scope",
    "current_version",
    "derive_seed",
    "event_scope",
    "fold",
    "generate",
    "generate_structured",
    "get_backend",
    "migrate",
    "migration",
    "persona_scope",
    "register",
    "register_schema",
]
