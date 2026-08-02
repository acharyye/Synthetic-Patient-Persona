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
