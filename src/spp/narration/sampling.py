"""Decode configuration, context-fit guard, and immutable model identity.

Three things that look like plumbing and are actually correctness:

**1. `num_ctx` is set explicitly and checked before every call.** Ollama's
default context window is small (2048-4096 depending on version) and it
*silently truncates the prompt head* when exceeded. A truncated take would
reproduce the exact signature of the degraded-canary configuration — starved
context, plausible-looking output — or worse, pass the gate while measuring a
prompt that is not the one we versioned. That is the same class of bug as a NaN
riding into `seed_path`: silent coercion upstream of a gate that cannot see it.
So the fit is checked here, and a take that would not fit is refused with its own
quarantine reason rather than being generated and scored.

**2. The model is pinned by digest, not tag.** `qwen2.5:7b-instruct` is a mutable
pointer: a registry update can change the weights, and the quantization, under
the same name. The digest is the immutable identity and is what belongs in the
ledger and on every take.

**3. Sampling parameters are part of the stamp.** `adapter_version` does not
cover them. Temperature 0 with a fixed seed gives per-machine stability, which is
what makes two eval runs comparable; cassettes make cross-machine determinism
moot, so this only has to be stable locally.
"""
from __future__ import annotations

import json
import urllib.request

from pydantic import BaseModel, Field


class SamplingConfig(BaseModel):
    """Everything that affects decode output. Frozen and stamped on every take."""

    model_config = {"frozen": True}

    num_ctx: int = Field(8192, gt=0, description="context window, set explicitly")
    num_predict: int = Field(700, gt=0)
    temperature: float = Field(0.0, ge=0.0)
    top_p: float = Field(1.0, gt=0.0, le=1.0)
    seed: int = 42

    def as_options(self) -> dict:
        """The `options` block for Ollama's /api/generate."""
        return {
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "seed": self.seed,
        }

    def stamp(self) -> dict:
        return self.model_dump()


DEFAULT_SAMPLING = SamplingConfig()

# Conservative characters-per-token. Real tokenizers average ~4 for English; 3.0
# deliberately OVER-estimates token count so the guard errs toward refusing a
# take rather than letting a silently-truncated one through.
CHARS_PER_TOKEN = 3.0


class ContextOverflow(RuntimeError):
    """The prompt plus the reservation would not fit in the context window."""

    def __init__(self, estimated: int, config: SamplingConfig) -> None:
        super().__init__(
            f"prompt ~{estimated} tokens + num_predict {config.num_predict} "
            f"exceeds num_ctx {config.num_ctx}. Ollama would silently truncate the "
            "prompt head, which looks identical to a starved-context degradation. "
            "Raise num_ctx or shorten the prompt (fewer retrieved facts)."
        )
        self.estimated = estimated
        self.config = config


def estimate_tokens(text: str) -> int:
    """Conservative token estimate. Over-estimates on purpose."""
    return int(len(text) / CHARS_PER_TOKEN) + 1


def context_fits(
    system: str, user: str, config: SamplingConfig = DEFAULT_SAMPLING
) -> tuple[bool, int]:
    """Would this prompt fit, leaving room for the reply? Returns (fits, estimate)."""
    estimated = estimate_tokens(system) + estimate_tokens(user)
    return (estimated + config.num_predict) <= config.num_ctx, estimated


def require_context_fits(
    system: str, user: str, config: SamplingConfig = DEFAULT_SAMPLING
) -> int:
    fits, estimated = context_fits(system, user, config)
    if not fits:
        raise ContextOverflow(estimated, config)
    return estimated


def resolve_model_digest(model: str, host: str | None = None) -> str | None:
    """Ask Ollama for the immutable digest behind a mutable tag.

    Returns None when Ollama is unreachable — the caller decides whether that is
    fatal. Recording without a digest is: a cassette that cannot name the weights
    it came from is not evidence about a model.
    """
    from ..config import settings

    base = (host or settings.ollama_host).rstrip("/")
    try:
        request = urllib.request.Request(
            f"{base}/api/show",
            data=json.dumps({"name": model}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            payload = json.loads(response.read())
    except Exception:
        return None

    digest = payload.get("digest") or (payload.get("details") or {}).get("digest")
    if not digest:
        # Older Ollama exposes it on the model list instead.
        try:
            with urllib.request.urlopen(f"{base}/api/tags", timeout=15) as response:  # noqa: S310
                for entry in json.loads(response.read()).get("models", []):
                    if entry.get("name") == model:
                        digest = entry.get("digest")
                        break
        except Exception:
            return None
    return digest


def model_identity(model: str, digest: str | None) -> str:
    """The identity that goes on a take. Digest when known, tag otherwise."""
    return f"{model}@{digest[:19]}" if digest else model


def model_is_resident(model: str, host: str | None = None) -> bool | None:
    """Is the model already loaded in the server, or would this call load it?

    Returns None when the server cannot be reached.

    This is not housekeeping. A cold load and a warm one produce **different
    output for identical inputs**, measured on 2026-08-23: the same battery,
    same digest, same (seed, temperature, top_p, num_predict, num_ctx), scored
    system_recall 0.5862 / state_coverage 0.5641 from a cold load and 0.6034 /
    0.5897 warm. Each state is internally exact — two warm runs matched to four
    decimal places, and a deliberate unload reproduced the cold figures exactly —
    so this is a hidden VARIABLE, not noise.

    That is the environment-declaration rule with a hole in it. The digest pins
    the weights and the sampling stamp pins the decode, but neither says whether
    the server had to load the model, and two bundles that disagree on it are not
    comparable.
    """
    from ..config import settings

    base = (host or settings.ollama_host).rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/ps", timeout=15) as response:  # noqa: S310
            payload = json.loads(response.read())
    except Exception:
        return None
    return any(entry.get("name") == model for entry in payload.get("models", []))


def warm_up(model: str, config: SamplingConfig = DEFAULT_SAMPLING) -> bool:
    """Force the model resident before a run, so every run starts warm.

    Stamping the load state would only let a reader know two bundles are
    incomparable. Making the state the same every time lets them BE comparable,
    which is the better fix — so this is called before scoring rather than merely
    recorded alongside it.

    The request carries the run's own decode options — `num_ctx` above all,
    because Ollama reloads the model when it changes and a reload would undo the
    warm-up — and its output is discarded.

    It is also SCHEMA-CONSTRAINED, for a reason learned by losing a recording to
    it: the first constrained call against a freshly loaded model pays for
    grammar construction as well as weights, and that combined first cost is what
    blew the adapter's timeout mid-record. Paying it here means the first SCORED
    call is never the first expensive one.
    """
    from ..foundation.llm import generate as llm_generate

    if model_is_resident(model):
        return True
    warmup_schema = {
        "type": "object",
        "properties": {"ok": {"type": "string", "enum": ["ok"]}},
        "required": ["ok"],
    }
    try:
        llm_generate("You are a warm-up request. Reply with {\"ok\": \"ok\"}.",
                     "ok", max_tokens=config.num_predict, schema=warmup_schema,
                     options=config.as_options())
    except Exception:
        return False
    return bool(model_is_resident(model))
