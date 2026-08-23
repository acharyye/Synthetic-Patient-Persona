"""LLM adapter: one interface, swappable backends, offline by default.

The offline-first promise means the core workflows must run with no model at all.
So the *default* backend is `NullBackend`, which returns deterministic
template text — not an error, not a stub that throws. CI runs the whole
simulation suite through it (roadmap §9: "the null backend must always keep core
workflows functional").

Backends:
  null       deterministic templates, no I/O                      (default)
  ollama     local model over http://localhost:11434              (offline-first)
  anthropic  cloud, opt-in only                                   (off by default)

Selection is `settings.llm_backend`, with `SPP_LIVE=false` forcing null
regardless — one switch that guarantees no external call.

The simulate/narrate separation (roadmap §2) means nothing here ever decides an
outcome. This layer only verbalises decisions the deterministic core already
made. If you find yourself wanting an LLM call to change simulation state, the
design has gone wrong.
"""
from __future__ import annotations

import json
from typing import Any, Protocol

from pydantic import BaseModel

from ..config import settings


class LLMResult(BaseModel):
    text: str
    backend: str
    model: str | None = None
    # True when the text came from a template rather than a model, so callers
    # and reports can label it honestly instead of passing it off as generated.
    synthetic: bool = False


class LLMBackend(Protocol):
    name: str

    def generate(self, system: str, prompt: str, max_tokens: int = 600,
                 schema: dict | None = None, options: dict | None = None) -> LLMResult: ...


class NullBackend:
    """Deterministic, dependency-free text. Keeps every workflow runnable offline.

    Deliberately labelled: the output says what it is, so an offline run is never
    mistaken for a real generation in a screenshot or an exported report.
    """

    name = "null"

    def generate(self, system: str, prompt: str, max_tokens: int = 600,
                 schema: dict | None = None, options: dict | None = None) -> LLMResult:
        return LLMResult(
            text=(
                "[offline] I can only answer from what's on file for me. "
                "Set SPP_LIVE=true with a configured backend for a generated reply."
            ),
            backend=self.name,
            synthetic=True,
        )


class OllamaBackend:
    """Local model over Ollama's HTTP API. No SDK dependency — just JSON."""

    name = "ollama"

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or settings.ollama_model
        self.host = (host or settings.ollama_host).rstrip("/")

    def generate(self, system: str, prompt: str, max_tokens: int = 600,
                 schema: dict | None = None, options: dict | None = None) -> LLMResult:
        import urllib.request

        # num_ctx MUST be explicit. Ollama's default is small and it silently
        # truncates the prompt head, which is indistinguishable downstream from a
        # deliberately starved context.
        decode_options = {"num_predict": max_tokens}
        decode_options.update(options or {})
        payload: dict = {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "options": decode_options,
        }
        if schema is not None:
            # Schema-constrained decoding: the grammar makes malformed output —
            # including a fabricated fact id, since fact_ids is an enum — not
            # merely unlikely but ungrammatical.
            payload["format"] = schema
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            f"{self.host}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=settings.ollama_timeout
        ) as response:
            payload = json.loads(response.read())
        return LLMResult(
            text=payload.get("response", "").strip(),
            backend=self.name,
            model=self.model,
        )


class AnthropicBackend:
    """Cloud backend. Opt-in: never selected unless explicitly configured."""

    name = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or settings.anthropic_model
        self.api_key = api_key or settings.anthropic_api_key

    def generate(self, system: str, prompt: str, max_tokens: int = 600,
                 schema: dict | None = None, options: dict | None = None) -> LLMResult:
        from anthropic import Anthropic

        client = Anthropic(api_key=self.api_key)
        if schema is not None:
            # No native grammar constraint here; instruct instead, and rely on
            # the structural gate. Recorded cassettes will show the difference.
            system = (
                f"{system}\n\nRespond with ONLY a JSON object matching this "
                f"schema:\n{json.dumps(schema)}"
            )
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        return LLMResult(text=text, backend=self.name, model=self.model)


_BACKENDS: dict[str, type] = {
    "null": NullBackend,
    "ollama": OllamaBackend,
    "anthropic": AnthropicBackend,
}


def get_backend(name: str | None = None) -> LLMBackend:
    """Resolve the active backend.

    `SPP_LIVE=false` forces null whatever else is configured — a single switch
    that guarantees no external call, which is what makes the offline claim
    checkable rather than aspirational.
    """
    if not settings.spp_live:
        return NullBackend()

    choice = (name or settings.llm_backend or "null").lower()
    backend_cls = _BACKENDS.get(choice)
    if backend_cls is None:
        raise ValueError(
            f"unknown LLM backend {choice!r}; expected one of {sorted(_BACKENDS)}"
        )

    # Refuse to hand back a cloud backend that cannot work; falling back to null
    # is better than a confusing auth error deep in a simulation run.
    if choice == "anthropic" and not settings.anthropic_api_key:
        print("[llm] anthropic backend selected but no API key set; using null backend")
        return NullBackend()

    return backend_cls()


def generate(system: str, prompt: str, max_tokens: int = 600,
             backend: str | None = None, schema: dict | None = None,
             options: dict | None = None) -> LLMResult:
    """Generate text, degrading to the null backend on any backend failure.

    A narration call must never take down a simulation: the deterministic core
    has already decided what happened, and this only describes it.
    """
    active = get_backend(backend)
    try:
        return active.generate(system, prompt, max_tokens=max_tokens,
                               schema=schema, options=options)
    except Exception as exc:  # pragma: no cover - env dependent
        print(f"[llm] {active.name} backend failed ({exc}); falling back to null")
        return NullBackend().generate(system, prompt, max_tokens=max_tokens)


def generate_structured(
    system: str,
    prompt: str,
    schema: dict[str, Any],
    max_tokens: int = 600,
    retries: int = 2,
    backend: str | None = None,
) -> dict | None:
    """Ask for JSON matching `schema`, retrying with a repair instruction.

    Returns None rather than raising when nothing parseable comes back, so the
    caller can fall back to a deterministic path.
    """
    instruction = (
        f"{system}\n\nRespond with ONLY a JSON object matching this schema:\n"
        f"{json.dumps(schema, indent=2)}\nNo prose, no markdown fences."
    )
    attempt_prompt = prompt

    for attempt in range(retries + 1):
        result = generate(instruction, attempt_prompt, max_tokens=max_tokens, backend=backend)
        if result.synthetic:
            return None  # offline: no structured output to give

        text = result.text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.lower().startswith("json"):
                text = text[4:]

        try:
            parsed = json.loads(text.strip())
        except json.JSONDecodeError as exc:
            if attempt == retries:
                print(f"[llm] structured output unparseable after {retries + 1} tries")
                return None
            attempt_prompt = (
                f"{prompt}\n\nYour previous reply was not valid JSON ({exc}). "
                "Return only the JSON object."
            )
            continue

        if isinstance(parsed, dict):
            return parsed
        return None

    return None
