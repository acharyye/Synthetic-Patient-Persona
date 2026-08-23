"""Record-replay cassettes for model calls.

The narration layer is the only nondeterministic thing in the system. Cassettes
quarantine it: a live run *records* `prompt_fingerprint -> response`, and every
offline run *replays*. The 477 offline tests stay offline and stay fast; live
tests sit behind a marker and are the only thing that needs a model.

Cassettes carry the model id and the adapter version, and `require_compatible()`
raises on mismatch — the same pattern as `EventLog.require_compatible()`, for the
same reason. Replaying a recording made by a different model would silently
answer today's question with yesterday's model's words, and every downstream
faithfulness number would be measuring the wrong thing.

**The model is an assumption.** It is registered in the ledger like any
coefficient, and swapping it is a ledger change that invalidates cassettes and
requires re-recording — not a config tweak.

**Cassettes are recordings, not goldens — so the record path is gated.** A
recording made from a non-compliant response would replay `grounded: True`
forever, which is exactly the trap that produced an eval set measuring stability
instead of relevance. So only responses that pass the citation gate are eligible
to persist; failures are written to a quarantine file with their reason, which
doubles as the compliance dataset the eval scores.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

CASSETTE_VERSION = 1
CASSETTE_DIR = Path(__file__).resolve().parents[3] / "tests" / "cassettes"


class CassetteMismatch(RuntimeError):
    """A cassette cannot be replayed against the current configuration."""


class CassetteMiss(KeyError):
    """No recording for this prompt. In replay-only mode that is a hard failure."""


class Take(BaseModel):
    """One recorded exchange."""

    fingerprint: str
    prompt_version: int
    system: str
    user: str
    response: str
    # The (prompt, model, adapter) triple this take belongs to. Compliance
    # numbers attach to a specific configuration or they are anecdotes.
    model: str = ""
    # Immutable weights identity. A tag is a mutable pointer; a cassette that
    # cannot name the weights it came from is not evidence about a model.
    model_digest: str = ""
    adapter_version: int = CASSETTE_VERSION
    # adapter_version does not cover decode settings, and they change output.
    sampling: dict = Field(default_factory=dict)


class QuarantinedTake(Take):
    """A response that failed the gate. Never replayed; kept as eval data."""

    failure_reason: str
    checked_at: str = ""


class Cassette(BaseModel):
    cassette_version: int = CASSETTE_VERSION
    name: str
    backend: str
    model: str
    prompt_version: int = 0
    takes: dict[str, Take] = Field(default_factory=dict)

    def require_compatible(
        self, backend: str, model: str, prompt_version: int | None = None
    ) -> Cassette:
        """Raise unless this cassette was recorded by the current configuration."""
        if self.cassette_version != CASSETTE_VERSION:
            raise CassetteMismatch(
                f"cassette {self.name!r} is v{self.cassette_version}, this build "
                f"reads v{CASSETTE_VERSION}. Re-record it."
            )
        if prompt_version is not None and self.prompt_version not in (0, prompt_version):
            raise CassetteMismatch(
                f"cassette {self.name!r} was recorded against prompt v"
                f"{self.prompt_version}, but the current prompt is v{prompt_version}. "
                "A prompt change invalidates recordings: re-record and re-run the "
                "narration evals."
            )
        if (self.backend, self.model) != (backend, model):
            raise CassetteMismatch(
                f"cassette {self.name!r} was recorded with {self.backend}/{self.model}, "
                f"but the current backend is {backend}/{model}. The model is an "
                "assumption: swapping it invalidates recordings, so re-record and "
                "re-run the narration evals rather than replaying these."
            )
        return self

    def get(self, fingerprint: str) -> Take | None:
        return self.takes.get(fingerprint)

    def put(self, take: Take) -> None:
        self.takes[take.fingerprint] = take


def cassette_path(name: str, directory: Path = CASSETTE_DIR) -> Path:
    return directory / f"{name}.json"


def load_cassette(name: str, directory: Path = CASSETTE_DIR) -> Cassette | None:
    path = cassette_path(name, directory)
    if not path.exists():
        return None
    return Cassette.model_validate(json.loads(path.read_text(encoding="utf-8")))


def save_cassette(cassette: Cassette, directory: Path = CASSETTE_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = cassette_path(cassette.name, directory)
    payload = cassette.model_dump()
    # Sorted so a re-record produces a reviewable diff rather than a reshuffle.
    payload["takes"] = dict(sorted(payload["takes"].items()))
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


class CassetteAdapter:
    """Wraps the LLM adapter with record/replay.

    Modes:
      `replay`  — cassette only; a miss raises. What CI uses.
      `record`  — call the model, store the take. What a live run uses.
      `auto`    — replay when present, otherwise record. Local development.
    """

    def __init__(
        self,
        name: str,
        mode: str = "replay",
        directory: Path = CASSETTE_DIR,
        backend: str | None = None,
        model: str | None = None,
    ) -> None:
        from ..config import settings

        self.name = name
        self.mode = mode
        self.directory = directory
        self.backend = backend or settings.llm_backend
        self.model = model or (
            settings.ollama_model if self.backend == "ollama" else settings.anthropic_model
        )

        existing = load_cassette(name, directory)
        if existing is not None:
            existing.require_compatible(self.backend, self.model)
        self.cassette = existing or Cassette(
            name=name, backend=self.backend, model=self.model
        )

    def generate(self, system: str, user: str, fingerprint: str,
                 max_tokens: int = 600) -> str:
        take = self.cassette.get(fingerprint)
        if take is not None:
            return take.response

        if self.mode == "replay":
            raise CassetteMiss(
                f"no recording for prompt {fingerprint[:12]} in cassette "
                f"{self.name!r}. Re-record with SPP_CASSETTE_MODE=record and a "
                "live backend, then commit the cassette."
            )

        from ..foundation.llm import generate as llm_generate

        result = llm_generate(system, user, max_tokens=max_tokens)
        self.cassette.put(Take(
            fingerprint=fingerprint,
            prompt_version=0,
            system=system,
            user=user,
            response=result.text,
        ))
        return result.text

    def save(self) -> Path:
        return save_cassette(self.cassette, self.directory)


class RecorderRejected(RuntimeError):
    """A response failed the citation gate and was not recorded."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"response rejected by the recorder gate: {reason}")
        self.reason = reason


class GatedRecorder:
    """Records only what passes the gate; quarantines the rest.

    The rule that keeps cassettes honest: a recording is a claim that this
    (prompt, model) produced a *groundable* answer. Persisting a failure would
    turn a one-off model lapse into a permanent green test.

    Quarantined takes are not waste — they are the compliance dataset. The eval
    reads them to report failure modes per configuration.
    """

    def __init__(
        self,
        name: str,
        directory: Path = CASSETTE_DIR,
        backend: str | None = None,
        model: str | None = None,
        prompt_version: int = 0,
        model_digest: str = "",
        sampling: dict | None = None,
        fresh: bool = False,
    ) -> None:
        from ..config import settings

        self.name = name
        self.directory = directory
        self.backend = backend or settings.llm_backend
        self.model = model or (
            settings.ollama_model if self.backend == "ollama" else settings.anthropic_model
        )
        self.prompt_version = prompt_version
        self.model_digest = model_digest
        self.sampling = sampling or {}

        # `fresh` is a deliberate re-record: start a new cassette rather than
        # appending to the one on disk. The compatibility check exists to stop an
        # APPEND that would mix two configurations in one file — it has nothing
        # to say about starting over, and making the intent a parameter beats
        # expressing it by moving files out from under the constructor.
        existing = None if fresh else load_cassette(name, directory)
        if existing is not None:
            existing.require_compatible(self.backend, self.model, prompt_version)
        self.cassette = existing or Cassette(
            name=name, backend=self.backend, model=self.model,
            prompt_version=prompt_version,
        )
        self.cassette.prompt_version = prompt_version
        self.quarantine: list[QuarantinedTake] = []

    def offer(
        self, fingerprint: str, system: str, user: str, response: str, *, passed: bool,
        reason: str = "",
    ) -> bool:
        """Offer a response for recording. Returns whether it was accepted."""
        from datetime import datetime, timezone

        take_kwargs = dict(
            fingerprint=fingerprint, prompt_version=self.prompt_version,
            system=system, user=user, response=response,
            model=self.model, model_digest=self.model_digest,
            adapter_version=CASSETTE_VERSION, sampling=self.sampling,
        )
        if passed:
            self.cassette.put(Take(**take_kwargs))
            return True

        self.quarantine.append(QuarantinedTake(
            **take_kwargs,
            failure_reason=reason or "failed the citation gate",
            checked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ))
        return False

    @property
    def accepted(self) -> int:
        return len(self.cassette.takes)

    @property
    def rejected(self) -> int:
        return len(self.quarantine)

    @property
    def compliance_rate(self) -> float | None:
        total = self.accepted + self.rejected
        return round(self.accepted / total, 4) if total else None

    def save(self) -> dict[str, Path | None]:
        """Persist the cassette, and the quarantine alongside it if non-empty."""
        cassette_file = save_cassette(self.cassette, self.directory)
        quarantine_file = None
        if self.quarantine:
            quarantine_file = self.directory / f"{self.name}.quarantine.json"
            quarantine_file.write_text(
                json.dumps({
                    "name": self.name,
                    "backend": self.backend,
                    "model": self.model,
                    "model_digest": self.model_digest,
                    "sampling": self.sampling,
                    "prompt_version": self.prompt_version,
                    "compliance_rate": self.compliance_rate,
                    "reason_counts": self.reason_counts(),
                    "rejected": [q.model_dump() for q in self.quarantine],
                }, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        return {"cassette": cassette_file, "quarantine": quarantine_file}


def _reason_counts(quarantine) -> dict[str, int]:
    counts: dict[str, int] = {}
    for take in quarantine:
        # Bucket by the leading clause so context overflows are separable from
        # genuine model non-compliance in the summary.
        key = take.failure_reason.split(";")[0].strip()
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


GatedRecorder.reason_counts = lambda self: _reason_counts(self.quarantine)

# Distinct reason so a truncated-context refusal is never mistaken for the model
# failing to ground — they have identical downstream symptoms otherwise.
CONTEXT_OVERFLOW_REASON = "context_overflow"


def archive_cassette(name: str, directory: Path = CASSETTE_DIR) -> Path | None:
    """Move an existing cassette aside, timestamped. Archive, never delete.

    A PROMPT_VERSION bump invalidates recordings and `GatedRecorder` refuses to
    append to them — correctly, because a recording made under a different
    prompt measured a different configuration. But refusing left the operator
    hand-moving files, so the deliberate step was improvised rather than
    supported.

    Preservation does not live here. The evidence bundle holds the sampled
    takes, the full quarantine and the aggregates, and git holds the file; this
    archive is a convenience for the person mid-re-record, not the record of
    what was measured.
    """
    path = cassette_path(name, directory)
    if not path.exists():
        return None

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = directory / "archive" / f"{name}.{stamp}"
    target.mkdir(parents=True, exist_ok=True)

    moved = []
    for suffix in ("", ".quarantine", ".compliance"):
        source = directory / f"{name}{suffix}.json"
        if source.exists():
            source.rename(target / source.name)
            moved.append(source.name)

    (target / "README.md").write_text(
        f"# Archived cassette: {name}\n\n"
        f"Archived {stamp} by `record_narration.py --rerecord`.\n\n"
        "These recordings measured a configuration that is no longer current —\n"
        "usually a PROMPT_VERSION bump. They are kept for convenience during a\n"
        "re-record, not as evidence.\n\n"
        "**The record of what was measured is the evidence bundle**\n"
        "(`evidence/<release>/<timestamp>/`): sampled takes, the full quarantine,\n"
        "aggregates and the pass-bar verdicts. Git holds the file history.\n\n"
        f"Files: {', '.join(moved)}\n",
        encoding="utf-8",
    )
    return target
