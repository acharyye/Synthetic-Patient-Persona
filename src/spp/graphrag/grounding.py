"""Assemble retrieved edges into a compact, citeable grounding block that the
persona engine injects into its prompt. Keeping citations explicit is what
separates this from 'prompt an LLM to roleplay a patient'.
"""
from __future__ import annotations

from ..graph.schema import NOISY_METAEDGES

# Hetionet's disease-presents-symptom edges come from MEDLINE co-occurrence
# rather than clinical curation, so a few are junk ("Birth Weight" as a symptom
# of type 2 diabetes). Telling the model that up front is cheaper and more honest
# than filtering silently — and filtering would hide the provenance problem
# rather than fix it.
_NOISE_CAVEAT = (
    "Some symptom links are literature co-occurrence, not curated clinical fact. "
    "If one looks implausible for you, simply don't mention it — never explain "
    "the knowledge graph itself."
)


def build_grounding(edges: list[dict]) -> str:
    if not edges:
        return (
            "No grounded facts retrieved. Speak only from your own profile above, "
            "and say you don't know rather than inventing clinical detail."
        )

    lines = []
    for e in edges:
        cite = f"  [{e['cite']}]" if e.get("cite") else ""
        lines.append(f"- {e['source']} --{e['rel']}--> {e['target']}{cite}")

    block = "Grounded knowledge-graph facts (do not contradict these):\n" + "\n".join(lines)

    if any(e.get("cite", "").rsplit(":", 1)[-1] in NOISY_METAEDGES for e in edges):
        block += f"\n\nNote: {_NOISE_CAVEAT}"
    return block
