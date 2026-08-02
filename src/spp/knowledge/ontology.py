"""A small owned ontology — deliberately small.

Hetionet gave us 47k nodes we did not author and could not fully vouch for. This
replaces it with a graph we own end to end: nine node kinds, eight edge kinds,
every fact carrying its own source and confidence. A small graph you understand
beats a big one you don't, and grounding a patient's words is a place where
"I can defend every edge" matters more than coverage.

The chain that makes this useful for a persona talking about a trial:

    Condition -PRESENTS-> Symptom
    Condition -TREATED_BY-> Treatment -CAUSES-> AdverseEffect
    Treatment -REQUIRES-> Procedure -IMPOSES-> Requirement
    Requirement -BLOCKED_BY-> Barrier -MITIGATED_BY-> Resource

The last three links are the ones no public biomedical KG has: they connect
clinical facts to *participation* facts, and `Barrier` node ids deliberately match
the barrier names the simulation already derives (`traits.barrier_severity`), so a
persona's simulated barriers resolve straight into citable graph facts.
"""
from __future__ import annotations

from typing import Literal

NodeKind = Literal[
    "Condition",
    "Stage",
    "Symptom",
    "Treatment",
    "AdverseEffect",
    "Procedure",
    "Requirement",
    "Barrier",
    "Resource",
]

EdgeKind = Literal[
    "PRESENTS",
    "HAS_STAGE",
    "TREATED_BY",
    "CAUSES",
    "REQUIRES",
    "IMPOSES",
    "BLOCKED_BY",
    "MITIGATED_BY",
]

NODE_KINDS: frozenset[str] = frozenset(NodeKind.__args__)
EDGE_KINDS: frozenset[str] = frozenset(EdgeKind.__args__)

# Every edge kind's legal (subject kind, object kind). Enforced at load, so a
# graph pack cannot express a relationship the ontology does not define.
EDGE_SIGNATURES: dict[str, tuple[str, str]] = {
    "PRESENTS": ("Condition", "Symptom"),
    "HAS_STAGE": ("Condition", "Stage"),
    "TREATED_BY": ("Condition", "Treatment"),
    "CAUSES": ("Treatment", "AdverseEffect"),
    "REQUIRES": ("Treatment", "Procedure"),
    "IMPOSES": ("Procedure", "Requirement"),
    "BLOCKED_BY": ("Requirement", "Barrier"),
    "MITIGATED_BY": ("Barrier", "Resource"),
}

# Human-readable phrasing per edge kind, used when a fact is rendered into a
# prompt. Kept here so the ontology owns its own wording.
EDGE_PHRASING: dict[str, str] = {
    "PRESENTS": "{subject} can cause {object}",
    "HAS_STAGE": "{subject} is staged as {object}",
    "TREATED_BY": "{subject} is treated with {object}",
    "CAUSES": "{subject} can cause the side effect {object}",
    "REQUIRES": "{subject} requires {object}",
    "IMPOSES": "{subject} means {object}",
    "BLOCKED_BY": "{subject} is difficult if {object}",
    "MITIGATED_BY": "{subject} can be eased by {object}",
}

# Retrieval walks these in order from an anchor Condition. Bounded and explicit:
# no variable-length traversal, so what a persona can cite is a design decision
# rather than an emergent property of the graph.
TRAVERSAL_PLAN: tuple[tuple[str, ...], ...] = (
    ("PRESENTS",),
    ("TREATED_BY",),
    ("TREATED_BY", "CAUSES"),
    ("TREATED_BY", "REQUIRES"),
    ("TREATED_BY", "REQUIRES", "IMPOSES"),
    ("TREATED_BY", "REQUIRES", "IMPOSES", "BLOCKED_BY"),
    ("TREATED_BY", "REQUIRES", "IMPOSES", "BLOCKED_BY", "MITIGATED_BY"),
)


def phrase(edge_kind: str, subject: str, object_: str) -> str:
    template = EDGE_PHRASING.get(edge_kind, "{subject} {kind} {object}")
    return template.format(subject=subject, object=object_, kind=edge_kind)
