"""Persona engine: conditions an LLM on Patient DNA + the grounded subgraph.

Narration only. Per the simulate/narrate separation, nothing here decides an
outcome — eligibility, burden and dropout are settled by the deterministic core
before a word is generated. This layer verbalises decisions already made.

Backend selection goes through `foundation.llm`, so offline behaviour is one
switch rather than a per-module fallback: with `SPP_LIVE=false` the null backend
returns deterministic text and no external call happens anywhere.
"""
from __future__ import annotations

from ..foundation import generate
from ..graph import GraphClient
from ..graphrag import build_grounding, retrieve_subgraph
from ..schemas import PatientDNA
from .prompts import SYSTEM_TEMPLATE


class PersonaEngine:
    def __init__(self, graph: GraphClient | None = None) -> None:
        self.graph = graph or GraphClient()

    def interview(self, dna: PatientDNA, message: str) -> dict:
        edges = retrieve_subgraph(self.graph, dna, message)
        grounding = build_grounding(edges)
        system = SYSTEM_TEMPLATE.format(dna_summary=dna.summary(), grounding=grounding)

        result = generate(system, message, max_tokens=600)
        reply = result.text
        if result.synthetic:
            # Keep the offline reply persona-shaped so downstream consumers see a
            # realistic payload, while `narration_backend` still says it's a template.
            reply = self._offline_reply(dna, message)

        return {
            "reply": reply,
            "grounded_edges": edges,
            "narration_backend": result.backend,
            "narration_synthetic": result.synthetic,
        }

    @staticmethod
    def _offline_reply(dna: PatientDNA, message: str) -> str:
        comorbidities = ", ".join(dna.comorbidities) or "everything else"
        return (
            f"[offline persona | {dna.condition}] You asked: '{message}'. "
            f"Managing this alongside {comorbidities} is a lot, and getting to "
            "appointments isn't always easy for me. "
            "(Set SPP_LIVE=true with an LLM backend for a generated reply.)"
        )
