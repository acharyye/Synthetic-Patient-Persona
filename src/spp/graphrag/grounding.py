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

    # Synthetic edges are announced IN THE BLOCK, not only on the edge object.
    # This string is what the model reads, so a flag that lives in the response
    # JSON and not here never reaches the thing that could be misled by it. The
    # offline stub's edges are shape demonstrations, and the persona has to know
    # that before it decides whether to mention them.
    synthetic = [e for e in edges if e.get("synthetic")]
    real = [e for e in edges if not e.get("synthetic")]

    lines = []
    for e in edges:
        cite = f"  [{e['cite']}]" if e.get("cite") else ""
        marker = "  (placeholder, not a retrieved fact)" if e.get("synthetic") else ""
        lines.append(f"- {e['source']} --{e['rel']}--> {e['target']}{cite}{marker}")

    block = "Grounded knowledge-graph facts (do not contradict these):\n" + "\n".join(lines)

    if synthetic:
        block += (
            f"\n\nNote: {len(synthetic)} of these {len(edges)} links are PLACEHOLDERS "
            "from the offline stub, not facts retrieved from any knowledge graph. "
            "They show the shape a real subgraph takes. Do not build an answer on "
            "them; if the persona has nothing real to say, say you don't know."
        )

    if any(e.get("cite", "").rsplit(":", 1)[-1] in NOISY_METAEDGES for e in real):
        block += f"\n\nNote: {_NOISE_CAVEAT}"
    return block
