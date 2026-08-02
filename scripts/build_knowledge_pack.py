"""Author the core knowledge pack.

    PYTHONPATH=src python scripts/build_knowledge_pack.py

Written as a script rather than hand-edited JSON because the pack has a lot of
repetition (every condition shares the same participation subgraph) and because
generating it means the ontology signatures are checked as it is built rather
than after. The JSON it emits is the artifact; this is how it was authored.

Sourcing note: clinical facts here are common, textbook-level associations —
the kind a patient would actually have been told — deliberately NOT scraped from
a biomedical KG. That is the point of a small owned graph: every edge is one
someone can defend. Confidence is `published_aggregate` for the clinical edges
and `expert_guess` for the participation-logistics edges, which are design
judgement about how trials burden people.
"""
from __future__ import annotations

import json
from datetime import date

from spp.knowledge.graph import KNOWLEDGE_DIR, KNOWLEDGE_SCHEMA_VERSION, KnowledgePack

AS_OF = date(2026, 8, 1).isoformat()

CLINICAL = {
    "source": "Standard clinical reference material; textbook-level associations.",
    "confidence": "published_aggregate",
    "as_of": AS_OF,
}
LOGISTICS = {
    "source": "Design judgement about trial participation demands.",
    "confidence": "expert_guess",
    "as_of": AS_OF,
}

# (condition id, display name, aliases, stages, symptoms, [(treatment, [AEs])])
CONDITIONS = [
    (
        "cond:t2d", "type 2 diabetes",
        ["t2d", "type 2 diabetes mellitus", "type ii diabetes", "diabetes"],
        ["early", "moderate", "advanced"],
        ["fatigue", "increased thirst", "frequent urination", "blurred vision",
         "slow-healing wounds", "numbness in the feet"],
        [("metformin", ["nausea", "diarrhoea", "metallic taste"]),
         ("empagliflozin", ["thrush", "dehydration", "urinary infection"]),
         ("semaglutide", ["nausea", "reduced appetite", "vomiting"]),
         ("insulin glargine", ["hypoglycaemia", "weight gain", "injection-site reaction"])],
    ),
    (
        "cond:copd", "COPD",
        ["chronic obstructive pulmonary disease", "emphysema"],
        ["GOLD1", "GOLD2", "GOLD3", "GOLD4"],
        ["breathlessness", "chronic cough", "wheezing", "chest tightness",
         "frequent chest infections", "fatigue"],
        [("salbutamol inhaler", ["tremor", "palpitations"]),
         ("tiotropium", ["dry mouth", "sore throat"]),
         ("inhaled corticosteroid", ["oral thrush", "hoarse voice", "chest infections"]),
         ("home oxygen", ["dry nose", "restricted mobility"])],
    ),
    (
        "cond:hf", "heart failure",
        ["chf", "congestive heart failure"],
        ["NYHA1", "NYHA2", "NYHA3", "NYHA4"],
        ["breathlessness", "ankle swelling", "fatigue", "palpitations",
         "difficulty lying flat"],
        [("ramipril", ["dry cough", "dizziness", "raised potassium"]),
         ("bisoprolol", ["fatigue", "cold hands and feet", "slow heart rate"]),
         ("spironolactone", ["raised potassium", "breast tenderness"]),
         ("furosemide", ["frequent urination", "dehydration", "dizziness"])],
    ),
    (
        "cond:breast_cancer", "breast cancer",
        ["breast carcinoma"],
        ["I", "II", "III", "IV"],
        ["breast lump", "skin changes", "fatigue", "pain"],
        [("anastrozole", ["hot flushes", "joint pain", "bone thinning"]),
         ("tamoxifen", ["hot flushes", "blood clots", "mood changes"]),
         ("paclitaxel", ["hair loss", "numbness in the hands", "fatigue"]),
         ("trastuzumab", ["heart strain", "chills", "fatigue"])],
    ),
    (
        "cond:ra", "rheumatoid arthritis",
        ["ra", "seropositive arthritis"],
        ["early", "moderate", "advanced"],
        ["joint pain", "morning stiffness", "joint swelling", "fatigue"],
        [("methotrexate", ["nausea", "mouth ulcers", "fatigue", "hair thinning"]),
         ("hydroxychloroquine", ["nausea", "rash"]),
         ("adalimumab", ["injection-site reaction", "infections"]),
         ("prednisolone", ["weight gain", "raised blood sugar", "bone thinning"])],
    ),
]

# Procedures a treatment implies, and what each one demands of a participant.
# Shared across conditions — this is the participation subgraph.
PROCEDURES = {
    "proc:bloods": ("fasting blood tests", [
        ("req:fasting", "you must not eat beforehand"),
        ("req:onsite", "you must attend the site in person"),
        ("req:weekday", "appointments are during working hours"),
    ]),
    "proc:monitoring": ("regular monitoring appointments", [
        ("req:onsite", "you must attend the site in person"),
        ("req:frequent", "visits repeat every few weeks"),
        ("req:weekday", "appointments are during working hours"),
    ]),
    "proc:imaging": ("scans", [
        ("req:onsite", "you must attend the site in person"),
        ("req:long_visit", "the appointment takes most of a day"),
    ]),
    "proc:diary": ("a daily symptom diary", [
        ("req:daily_task", "you must record something every day"),
        ("req:literacy", "you must read and complete forms yourself"),
    ]),
}

REQUIREMENTS = {
    "req:fasting": "you must not eat beforehand",
    "req:onsite": "you must attend the site in person",
    "req:weekday": "appointments are during working hours",
    "req:frequent": "visits repeat every few weeks",
    "req:long_visit": "the appointment takes most of a day",
    "req:daily_task": "you must record something every day",
    "req:literacy": "you must read and complete forms yourself",
}

# Barrier ids match the simulation's derived barrier names exactly, so a
# persona's simulated barriers resolve straight into citable facts.
BARRIERS = {
    "transport": "you have no reliable way to get to the site",
    "scheduling": "your work pattern clashes with appointment times",
    "cost": "travel and time off work cost money you do not have",
    "unsupported": "there is nobody at home to help you",
    "adherence": "keeping to a treatment routine is already hard for you",
    "mobility": "travelling and waiting are physically hard",
    "comprehension": "forms and instructions are hard to follow",
    "competing_care": "other conditions compete for the same appointments",
    "distance": "the site is a long journey away",
    "pill_burden": "your medication routine is already complicated",
    "digital_access": "app-based tasks are difficult for you",
    "transport_fragile": "your journey depends on public transport running",
}

# What blocks what.
BLOCKS = {
    "req:onsite": ["transport", "mobility", "distance", "transport_fragile", "cost"],
    "req:weekday": ["scheduling", "cost"],
    "req:frequent": ["scheduling", "transport", "competing_care", "cost"],
    "req:long_visit": ["scheduling", "mobility", "unsupported"],
    "req:daily_task": ["adherence", "comprehension", "digital_access"],
    "req:literacy": ["comprehension", "digital_access"],
    "req:fasting": ["competing_care", "adherence"],
}

RESOURCES = {
    "transport": ["a travel reimbursement scheme", "arranged patient transport"],
    "mobility": ["arranged patient transport", "ground-floor clinic rooms"],
    "distance": ["remote visits by video", "a local clinic partnership"],
    "transport_fragile": ["a travel reimbursement scheme", "remote visits by video"],
    "cost": ["a travel reimbursement scheme", "same-day expense payment"],
    "scheduling": ["evening and weekend clinic slots", "remote visits by video"],
    "unsupported": ["a study buddy or research nurse contact"],
    "adherence": ["reminder calls from the research nurse", "a simplified visit schedule"],
    "comprehension": ["plain-language study materials",
                      "a study buddy or research nurse contact"],
    "digital_access": ["paper alternatives to app tasks",
                       "plain-language study materials"],
    "competing_care": ["a simplified visit schedule",
                       "appointments combined with routine care"],
    "pill_burden": ["a simplified visit schedule"],
}

# Which procedures each treatment implies.
TREATMENT_PROCEDURES = {
    "insulin glargine": ["proc:monitoring", "proc:bloods", "proc:diary"],
    "metformin": ["proc:bloods"],
    "empagliflozin": ["proc:bloods", "proc:monitoring"],
    "semaglutide": ["proc:monitoring", "proc:diary"],
    "salbutamol inhaler": ["proc:diary"],
    "tiotropium": ["proc:monitoring"],
    "inhaled corticosteroid": ["proc:monitoring", "proc:diary"],
    "home oxygen": ["proc:monitoring", "proc:imaging"],
    "ramipril": ["proc:bloods", "proc:monitoring"],
    "bisoprolol": ["proc:monitoring"],
    "spironolactone": ["proc:bloods"],
    "furosemide": ["proc:bloods", "proc:monitoring"],
    "anastrozole": ["proc:monitoring", "proc:imaging"],
    "tamoxifen": ["proc:monitoring"],
    "paclitaxel": ["proc:monitoring", "proc:bloods", "proc:imaging"],
    "trastuzumab": ["proc:monitoring", "proc:imaging"],
    "methotrexate": ["proc:bloods", "proc:monitoring"],
    "hydroxychloroquine": ["proc:monitoring"],
    "adalimumab": ["proc:bloods", "proc:monitoring"],
    "prednisolone": ["proc:bloods"],
}


def slug(prefix: str, text: str) -> str:
    return f"{prefix}:" + text.lower().replace(" ", "_").replace("/", "_")


def main() -> None:
    nodes: dict[str, dict] = {}
    facts: list[dict] = []
    counter = [0]

    def add_node(node_id: str, kind: str, name: str, aliases=None, note="") -> str:
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id, "kind": kind, "name": name,
                "aliases": aliases or [], "note": note,
            }
        return node_id

    def add_fact(subject: str, predicate: str, object_: str, prov: dict,
                 qualifier: str = "") -> None:
        counter[0] += 1
        facts.append({
            "id": f"F{counter[0]:03d}",
            "subject": subject, "predicate": predicate, "object": object_,
            "provenance": prov, "qualifier": qualifier,
        })

    # Shared participation subgraph first, so its ids are low and stable.
    for req_id, text in REQUIREMENTS.items():
        add_node(req_id, "Requirement", text)
    for barrier_id, text in BARRIERS.items():
        add_node(f"barrier:{barrier_id}", "Barrier", text,
                 aliases=[barrier_id], note=f"matches simulated barrier {barrier_id!r}")
    for proc_id, (name, _) in PROCEDURES.items():
        add_node(proc_id, "Procedure", name)
    for resources in RESOURCES.values():
        for resource in resources:
            add_node(slug("res", resource), "Resource", resource)

    for proc_id, (_, requirements) in PROCEDURES.items():
        for req_id, _ in requirements:
            add_fact(proc_id, "IMPOSES", req_id, LOGISTICS)

    for req_id, barrier_ids in BLOCKS.items():
        for barrier_id in barrier_ids:
            add_fact(req_id, "BLOCKED_BY", f"barrier:{barrier_id}", LOGISTICS)

    for barrier_id, resources in RESOURCES.items():
        for resource in resources:
            add_fact(f"barrier:{barrier_id}", "MITIGATED_BY", slug("res", resource),
                     LOGISTICS)

    # Clinical subgraph per condition.
    for cond_id, name, aliases, stages, symptoms, treatments in CONDITIONS:
        add_node(cond_id, "Condition", name, aliases=aliases)
        for stage in stages:
            stage_id = slug(f"stage:{cond_id.split(':')[1]}", stage)
            add_node(stage_id, "Stage", stage)
            add_fact(cond_id, "HAS_STAGE", stage_id, CLINICAL)
        for symptom in symptoms:
            symptom_id = slug("sym", symptom)
            add_node(symptom_id, "Symptom", symptom)
            add_fact(cond_id, "PRESENTS", symptom_id, CLINICAL)
        for treatment, adverse in treatments:
            treatment_id = slug("tx", treatment)
            add_node(treatment_id, "Treatment", treatment)
            add_fact(cond_id, "TREATED_BY", treatment_id, CLINICAL)
            for effect in adverse:
                effect_id = slug("ae", effect)
                add_node(effect_id, "AdverseEffect", effect)
                add_fact(treatment_id, "CAUSES", effect_id, CLINICAL)
            for proc_id in TREATMENT_PROCEDURES.get(treatment, []):
                add_fact(treatment_id, "REQUIRES", proc_id, LOGISTICS)

    payload = {
        "schema_version": KNOWLEDGE_SCHEMA_VERSION,
        "name": "core",
        "description": (
            "Small owned ontology: five conditions with symptoms, treatments and "
            "side effects, joined to a shared participation subgraph of "
            "procedures, requirements, barriers and mitigating resources."
        ),
        "nodes": list(nodes.values()),
        "facts": facts,
    }

    pack = KnowledgePack.model_validate(payload)  # validate before writing
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    path = KNOWLEDGE_DIR / "core.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"wrote {path}  ({len(pack.nodes)} nodes, {len(pack.facts)} facts)")


if __name__ == "__main__":
    main()
