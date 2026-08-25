"""A take carries WHO it is about, so the join is by identity not reconstruction.

Third appearance of one bug. `synthetic-0000` was unique only within a cohort.
The compliance eval keyed on it and scored one condition's personas against
another's expected facts. And on 2026-08-25 a held-out validation joined archived
takes back to personas by QUESTION text — the battery has 30 cases over six
unique questions, five personas each — so 24 of 30 takes were scored against the
wrong persona's state surface, and every number computed from them was wrong.

Same fix all three times: make the key carry identity. These tests pin both
halves of it, including the half that would be expensive to get wrong.
"""
from datetime import date

from spp.cohort import generate_cohort
from spp.knowledge import load_graph
from spp.knowledge.retrieval import retrieve
from spp.narration.cassette import GatedRecorder
from spp.narration.prompt import build_prompt


def a_prompt():
    dna = generate_cohort("COPD", 6, seed=42, as_of=date(2026, 8, 1))[0]
    graph = load_graph()
    retrieval = retrieve(graph, dna.condition, "What makes getting there hard?",
                         limit=8, barriers=tuple(b.name for b in dna.barriers))
    return dna, build_prompt(dna, retrieval, "What makes getting there hard?")


class TestTheStamp:
    def test_the_prompt_knows_whose_it_is(self):
        dna, prompt = a_prompt()

        assert prompt.persona_id == dna.patient_id
        assert prompt.persona_id

    def test_persona_id_is_not_in_the_fingerprint(self):
        """Load-bearing. The fingerprint hashes what the model was SHOWN, and the
        persona is already in the system text. Folding the id in would change
        every cassette key without changing a single prompt, invalidating every
        recording ever made to gain nothing."""
        _, prompt = a_prompt()
        other = prompt.model_copy(update={"persona_id": "someone-else-0001"})

        assert other.fingerprint == prompt.fingerprint

    def test_the_recorder_stamps_it_through(self, tmp_path):
        dna, prompt = a_prompt()
        recorder = GatedRecorder("stamp-test", backend="null", model="m",
                                 prompt_version=prompt.prompt_version,
                                 directory=tmp_path, fresh=True)

        recorder.offer(prompt.fingerprint, prompt.system, prompt.user,
                       '{"segments": []}', passed=True,
                       persona_id=prompt.persona_id)

        take = recorder.cassette.get(prompt.fingerprint)
        assert take is not None
        assert take.persona_id == dna.patient_id

    def test_an_unstamped_take_is_legal_and_empty(self):
        """Takes recorded before 2026-08-25 have no stamp. They must still load —
        a migration that refuses the archive would delete the evidence the fix
        exists because of."""
        from spp.narration.cassette import Take

        take = Take(fingerprint="f", prompt_version=3, system="s", user="u",
                    response="r")

        assert take.persona_id == ""
