"""Every v2.2 frame is watched to fire before any aggregate is computed.

The canary principle at unit level. Each fixture sentence is authored FROM the
rule that names the frame — R1/BA3 for possession, R3/BA2 for experience, R5 for
ability and situation, R4 for negated resource — not lifted from a sheet, so
these assertions are independent of the text v2.2 will be scored on.

The ability fixture is the canary's own baseline sentence. v2.1 scored it as
carrying no circumstantial segment, which zeroed `state_coverage` and stopped
`test_the_state_lever_collapses_state_coverage` from firing at all. Canary
compatibility is an adoption criterion, so it is asserted here from birth rather
than discovered at the gate.
"""
import pytest

from spp.narration.frames import frames_firing, is_circumstantial_v22

FIXTURES = [
    ("possession", "I take salbutamol PRN and tiotropium."),
    ("experience", "Bisoprolol makes me feel tired and my hands get cold."),
    ("ability", "I cannot always get myself to the clinic."),
    ("situation", "The site is quite far away from me."),
    ("negated_resource", "I don't have a car."),
]


class TestEveryFrameFires:
    @pytest.mark.parametrize("frame,sentence", FIXTURES, ids=[f for f, _ in FIXTURES])
    def test_the_frame_fires_on_its_own_fixture(self, frame, sentence):
        assert frame in frames_firing(sentence)

    def test_all_five_are_covered(self):
        """A frame added to FRAMES without a fixture would slip through silently."""
        from spp.narration.frames import FRAMES

        assert set(FRAMES) == {frame for frame, _ in FIXTURES}


class TestTheNegativeControls:
    def test_the_clinical_class_fires_nothing(self):
        """R1's exemplar. First person is grammar, the claim is about a drug."""
        assert frames_firing("For the metformin, I need to do fasting blood tests.") == set()

    def test_a_bare_temporal_locator_fires_nothing(self):
        """BA1. 'during my work hours' presupposes employment; it asserts none."""
        assert frames_firing(
            "Tamoxifen also needs monitoring visits during my work hours."
        ) == set()

    def test_have_to_is_obligation_not_possession(self):
        assert frames_firing("I have to go see the doctor every few weeks.") == set()
        assert "possession" in frames_firing("I have a paid carer who helps.")

    def test_modal_talk_is_knowledge_not_experience(self):
        """BA2. 'can make me' is a property of the drug; 'makes me' happened."""
        assert "experience" not in frames_firing("Ramipril can make me feel dizzy.")
        assert "experience" in frames_firing("Ramipril makes me feel dizzy.")


class TestTheCanaryFixture:
    def test_the_ability_claim_is_circumstantial(self):
        """The exact sentence v2.1 failed on. If this regresses, adoption fails
        the canary criterion regardless of any sheet result."""
        state = frozenset({"transport", "clinic", "adherence"})
        graph = frozenset({"clinic"})

        assert is_circumstantial_v22(
            "I cannot always get myself to the clinic.", state, graph
        )

    def test_an_asserted_conflict_beats_a_locator(self):
        """BA1's two halves, same vocabulary, opposite verdicts."""
        state = frozenset({"work", "shift"})
        graph = frozenset()

        assert is_circumstantial_v22(
            "It is tough because of my shift work.", state, graph
        )
        assert not is_circumstantial_v22(
            "Tamoxifen needs monitoring visits during my work hours.", state, graph
        )
