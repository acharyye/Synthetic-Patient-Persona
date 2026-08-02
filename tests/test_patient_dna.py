from spp.schemas import PatientDNA


def test_summary_is_readable():
    dna = PatientDNA(patient_id="t1", age=70, sex="male", condition="COPD")
    s = dna.summary()
    assert "COPD" in s and "70yo male" in s


def test_adherence_bounds():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PatientDNA(patient_id="t2", age=70, sex="male", condition="COPD",
                   adherence_baseline=1.5)
