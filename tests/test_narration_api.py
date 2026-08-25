"""The narration surface at its HTTP boundary, offline (SPP_LIVE unset).

`/persona/narrate`, `/panel/run` and `/persona/interview` are the three endpoints
in front of the only nondeterministic layer in the system, and they were the
three with no test touching them at all. The layer *behind* them is covered hard
— prompt goldens, the citation gate, cassettes, memory semantics under
permutation — so what is missing is specifically the boundary: request
validation, what the response promises a consumer, and that offline still
produces a cited skeleton rather than prose.

Offline these run against the null backend, which emits a citation skeleton
rather than words. That is the correct thing to test here: everything except the
wording is exercised, and the wording is what a cassette covers.
"""
from fastapi.testclient import TestClient

from spp.api.main import app
from spp.cohort import generate_cohort

client = TestClient(app)

NARRATE = {
    "condition": "type 2 diabetes",
    "n": 3,
    "seed": 42,
    "persona_index": 0,
    "question": "What makes getting to appointments hard for you?",
}


# -- /persona/narrate -------------------------------------------------------

def test_narrate_returns_a_cited_answer_offline():
    body = client.post("/persona/narrate", json=NARRATE).json()

    assert body["question"] == NARRATE["question"]
    assert body["patient_id"].startswith("type-2-diabetes-s42-")
    assert body["answer_with_citations"]
    assert body["cited_fact_ids"], "the null backend must still cite"
    assert isinstance(body["grounded"], bool)
    assert "not regulatory evidence" in body["disclaimer"]


def test_narrate_hides_the_check_but_keeps_the_verdict():
    """`check` is excluded from the response; `grounded` is not.

    A consumer needs to know whether the answer verified. It does not need the
    checker's internals, and shipping them would invite a client to re-implement
    the gate against a shape that is free to change.
    """
    body = client.post("/persona/narrate", json=NARRATE).json()

    assert "check" not in body
    assert "grounded" in body


def test_narrate_rejects_a_persona_index_past_the_cohort():
    response = client.post("/persona/narrate", json={**NARRATE, "persona_index": 3})

    assert response.status_code == 400
    assert "persona_index" in response.json()["detail"]


def test_narrate_is_deterministic_offline():
    """Same request, same bytes. The cohort is seeded and the null backend is a
    function of the prompt, so a difference here is a leak of clock or RNG into
    a path that must not have one."""
    first = client.post("/persona/narrate", json=NARRATE).json()
    second = client.post("/persona/narrate", json=NARRATE).json()

    assert first == second


# -- /panel/run -------------------------------------------------------------

PANEL = {"condition": "COPD", "n": 6, "seed": 42, "topic": "weekly clinic visits"}


def test_panel_returns_a_transcript_sized_to_the_cohort():
    body = client.post("/panel/run", json=PANEL).json()

    assert body["topic"] == PANEL["topic"]
    assert body["panel_size"] == PANEL["n"]
    assert body["statements"], "a panel with no statements is not a panel"
    assert "not regulatory evidence" in body["disclaimer"]


def test_panel_themes_are_attributed_mechanically():
    """A theme's members must be personas that actually spoke, and its support
    must be the count of them — not a number the summary layer chose. Themes
    group by shared cited facts precisely so `3 of 6 raised travel` is a count
    over citations rather than a judgement call."""
    body = client.post("/panel/run", json=PANEL).json()

    speakers = {statement["patient_id"] for statement in body["statements"]}
    orders = {statement["order"] for statement in body["statements"]}

    for theme in body["themes"]:
        assert set(theme["patient_ids"]) <= speakers
        assert set(theme["statement_orders"]) <= orders
        assert theme["fact_ids"], "a theme with no shared facts has no grouping"


def test_panel_ungrounded_count_is_the_transcript_it_ships(monkeypatch):
    """Pinned against a transcript that actually contains an ungrounded
    statement, because offline every statement grounds.

    The obvious version of this test — recompute the count from the returned
    statements and compare — passes against an endpoint hard-wired to report 0,
    since both sides are 0 in a null-backend run. It was written that way first
    and a mutation proved it could not fail. Same species as a pass bar supplied
    as a literal: an assertion that cannot discriminate is not coverage.
    """
    from spp.narration.panel import PanelStatement, PanelTranscript

    transcript = PanelTranscript(
        topic=PANEL["topic"],
        panel_size=2,
        statements=[
            PanelStatement(order=0, patient_id="a", prompt="q", text="grounded",
                           cited_fact_ids=["F1"], grounded=True),
            PanelStatement(order=1, patient_id="b", prompt="q", text="ungrounded",
                           cited_fact_ids=[], grounded=False),
        ],
    )
    monkeypatch.setattr("spp.api.main.run_panel", lambda *a, **k: transcript)

    body = client.post("/panel/run", json=PANEL).json()

    assert body["ungrounded_statements"] == 1


def test_panel_rejects_a_size_outside_its_bounds():
    """2..12 is declared on the model. A one-person panel is not a focus group
    and an unbounded one is a cost, so both ends are asserted."""
    assert client.post("/panel/run", json={**PANEL, "n": 1}).status_code == 422
    assert client.post("/panel/run", json={**PANEL, "n": 13}).status_code == 422


def test_panel_is_deterministic_offline():
    first = client.post("/panel/run", json=PANEL).json()
    second = client.post("/panel/run", json=PANEL).json()

    assert first == second


# -- /persona/interview -----------------------------------------------------

def test_interview_answers_over_a_supplied_dna():
    """The legacy persona-engine surface: it takes a whole PatientDNA rather
    than generating one, and returns the retrieved edges it grounded on."""
    dna = generate_cohort("COPD", 1, seed=42)[0]
    body = client.post(
        "/persona/interview",
        json={"dna": dna.model_dump(mode="json"), "message": "How are you sleeping?"},
    ).json()

    assert body["reply"]
    assert isinstance(body["grounded_edges"], list)
    assert body["narration_backend"]
    assert body["narration_synthetic"] is True, "offline must not claim a model wrote this"
    assert "not regulatory evidence" in body["disclaimer"]


def test_interview_rejects_a_malformed_dna():
    """A typo'd persona payload must fail validation rather than be quietly
    filled with defaults — a persona built from defaults is a different persona."""
    response = client.post(
        "/persona/interview", json={"dna": {"condition": "COPD"}, "message": "hello"}
    )

    assert response.status_code == 422
