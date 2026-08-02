"""End-to-end checks over the FastAPI surface, offline (SPP_LIVE unset)."""
from fastapi.testclient import TestClient

from spp.api.main import app
from spp.cohort import generate_cohort
from spp.protocol import ProtocolBurden, burden_profile, rank_by_burden
from spp.schemas import Medication, PatientDNA

client = TestClient(app)


def test_health():
    """Passes offline and live — /health must report grounding honestly either
    way, so assert the fields are consistent rather than pinning a mode."""
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert isinstance(body["graph_live"], bool)
    if body["graph_live"]:
        assert body["graph_nodes"] > 0
    else:
        assert body["graph_nodes"] == 0


def test_protocol_fields_documents_the_grammar():
    body = client.get("/protocol/fields").json()
    assert "age" in body["fields"]
    assert "biomarkers.<key>" in body["fields"]
    assert any("in {" in s for s in body["syntax"])


def test_cohort_generate_returns_summary_and_people():
    body = client.post(
        "/cohort/generate", json={"condition": "COPD", "n": 12, "seed": 3}
    ).json()

    assert body["n"] == 12
    assert body["summary"]["n"] == 12
    assert len(body["cohort"]) == 12
    assert body["cohort"][0]["condition"] == "COPD"
    assert "not regulatory evidence" in body["disclaimer"]


def test_stress_test_screens_and_interviews():
    body = client.post(
        "/protocol/stress-test",
        json={
            "condition": "type 2 diabetes",
            "n": 40,
            "seed": 3,
            "inclusion": ["age >= 50", "biomarkers.HbA1c_pct >= 7.0"],
            "exclusion": ["biomarkers.eGFR < 45", "adherence_baseline < 0.5"],
            "burden": {"visits_per_year": 24, "daily_diary": True},
            "interview_top_n": 2,
        },
    ).json()

    screening = body["screening"]
    assert screening["n_screened"] == 40
    assert 0 <= screening["n_eligible"] <= 40
    assert len(screening["verdicts"]) == 40

    # Every criterion is accounted for, sorted by how much attrition it causes.
    criteria = [c["criterion"] for c in screening["criteria_impact"]]
    assert set(criteria) == {
        "age >= 50",
        "biomarkers.HbA1c_pct >= 7.0",
        "biomarkers.eGFR < 45",
        "adherence_baseline < 0.5",
    }
    counts = [c["screened_out"] for c in screening["criteria_impact"]]
    assert counts == sorted(counts, reverse=True)
    assert all(c["sole_reason"] <= c["screened_out"] for c in screening["criteria_impact"])

    assert len(body["interviews"]) == 2
    first = body["interviews"][0]
    assert first["response"]                 # stub reply offline, real reply live
    assert first["grounded_edges"]           # citations survive the round trip
    assert 0 <= first["score"] <= 1

    # Interviewees must have survived screening.
    eligible = {v["patient_id"] for v in screening["verdicts"] if v["eligible"]}
    assert {i["patient_id"] for i in body["interviews"]} <= eligible


def test_stress_test_rejects_a_malformed_criterion():
    response = client.post(
        "/protocol/stress-test",
        json={"condition": "COPD", "n": 5, "inclusion": ["bmi_at_screening > 30"]},
    )
    assert response.status_code == 400
    assert "unknown field" in response.json()["detail"]


def test_tighter_criteria_never_enrol_more_people():
    def eligible(inclusion: list[str]) -> int:
        return client.post(
            "/protocol/stress-test",
            json={
                "condition": "type 2 diabetes",
                "n": 60,
                "seed": 5,
                "inclusion": inclusion,
                "interview_top_n": 0,
            },
        ).json()["screening"]["n_eligible"]

    loose = eligible(["age >= 50"])
    tight = eligible(["age >= 50", "biomarkers.HbA1c_pct >= 8.0"])
    assert tight <= loose


def test_interviews_can_be_switched_off():
    body = client.post(
        "/protocol/stress-test",
        json={"condition": "COPD", "n": 10, "interview_top_n": 0},
    ).json()
    assert body["interviews"] == []


class TestBurdenScoring:
    def _patient(self, **overrides) -> PatientDNA:
        base = dict(
            patient_id="b1",
            age=70,
            sex="male",
            condition="COPD",
            adherence_baseline=0.9,
            health_literacy="high",
            social_determinants={
                "transport": "own car",
                "caregiver": "spouse",
                "employment": "retired",
                "residence": "urban",
            },
        )
        return PatientDNA(**{**base, **overrides})

    def test_unencumbered_patient_scores_low(self):
        assert burden_profile(self._patient()).score == 0.0

    def test_barriers_accumulate_and_are_named(self):
        blocked = self._patient(
            adherence_baseline=0.3,
            health_literacy="low",
            social_determinants={
                "transport": "none",
                "caregiver": "none",
                "employment": "shift-work",
                "residence": "rural",
            },
            comorbidities=["hypertension", "CKD", "depression"],
            medications=[Medication(name=f"drug{i}") for i in range(3)],
        )
        profile = burden_profile(blocked)

        assert profile.score > 0.7
        assert any("transport" in d for d in profile.drivers)
        assert any("literacy" in d for d in profile.drivers)

    def test_heavier_protocol_amplifies_existing_barriers(self):
        patient = self._patient(health_literacy="low", adherence_baseline=0.4)
        light = burden_profile(patient, ProtocolBurden(visits_per_year=2))
        heavy = burden_profile(
            patient, ProtocolBurden(visits_per_year=24, daily_diary=True)
        )
        assert heavy.score > light.score

    def test_heavier_protocol_adds_nothing_to_an_unencumbered_patient(self):
        patient = self._patient()
        heavy = burden_profile(patient, ProtocolBurden(visits_per_year=24, daily_diary=True))
        assert heavy.score == 0.0

    def test_ranking_puts_the_hardest_cases_first(self):
        cohort = generate_cohort("type 2 diabetes", 30, seed=29)
        ranked = rank_by_burden(cohort)
        assert [p.score for p in ranked] == sorted((p.score for p in ranked), reverse=True)
        assert {p.patient_id for p in ranked} == {p.patient_id for p in cohort}


class TestSimulationEndpoint:
    def test_run_returns_funnel_curve_and_breakdown(self):
        body = client.post(
            "/simulation/run",
            json={
                "condition": "COPD", "n": 80, "seed": 42,
                "inclusion": ["stage >= GOLD2"],
                "burden": {"visits_per_year": 12},
            },
        ).json()

        funnel = body["funnel"]
        assert funnel["screened"] == 80
        assert funnel["enrolled"] <= funnel["screened"]
        assert funnel["retained"] + funnel["dropped"] == funnel["enrolled"]

        curve = body["survival_curve"]
        assert curve[0]["retention"] == 1.0
        assert [p["retention"] for p in curve] == sorted(
            (p["retention"] for p in curve), reverse=True
        )
        assert set(body["burden_breakdown"]) == {
            "time", "travel", "procedural", "cognitive", "financial", "scheduling"
        }

    def test_a_lighter_protocol_retains_at_least_as_well(self):
        def retention(payload: dict) -> float:
            return client.post("/simulation/run", json=payload).json()["retention"][
                "retention_rate"
            ]

        base = {"condition": "COPD", "n": 80, "seed": 42}
        light = retention({**base, "burden": {"visits_per_year": 4,
                                              "travel_required": False}})
        heavy = retention({**base, "burden": {"visits_per_year": 24,
                                              "daily_diary": True}})
        assert heavy <= light

    def test_malformed_criteria_are_rejected(self):
        response = client.post(
            "/simulation/run",
            json={"condition": "COPD", "n": 10, "inclusion": ["not_a_field > 1"]},
        )
        assert response.status_code == 400

    def test_assumptions_endpoint_flags_the_unquotable(self):
        body = client.get("/assumptions").json()
        assert body["count"] >= 15
        assert "timeline.dropout_hazard" in body["unsupported"]
        assert "cohort.condition_priors" in body["unsupported"]
