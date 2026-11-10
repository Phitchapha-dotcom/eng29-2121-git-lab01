import pytest

from bjt import BiasInputs, ValidationError, parse_inputs, validate_inputs

VALID_FORM = {
    "vcc": "12",
    "r1": "47000",
    "r2": "10000",
    "rc": "2200",
    "re": "1000",
    "beta": "150",
    "vbe": "0.7",
}

VALID = BiasInputs(vcc=12, r1=47000, r2=10000, rc=2200, re=1000, beta=150, vbe=0.7)


def test_parse_valid_form():
    assert parse_inputs(VALID_FORM) == VALID


@pytest.mark.parametrize("field", ["vcc", "r1", "r2", "rc", "re", "beta", "vbe"])
def test_missing_field_is_rejected(field):
    raw = dict(VALID_FORM)
    del raw[field]
    with pytest.raises(ValidationError) as exc:
        parse_inputs(raw)
    assert exc.value.field == field


@pytest.mark.parametrize("field", ["vcc", "r1", "r2", "rc", "re", "beta", "vbe"])
def test_non_numeric_field_is_rejected(field):
    raw = dict(VALID_FORM)
    raw[field] = "47,000"
    with pytest.raises(ValidationError) as exc:
        parse_inputs(raw)
    assert exc.value.field == field


@pytest.mark.parametrize(
    "field,value",
    [
        ("vcc", "0"),
        ("vcc", "-1"),
        ("r1", "0"),
        ("r2", "-1"),
        ("rc", "0"),
        ("re", "0"),
        ("beta", "0.5"),
        ("vbe", "0"),
        ("vbe", "12"),
    ],
)
def test_range_rules_are_enforced(field, value):
    raw = dict(VALID_FORM)
    raw[field] = value
    with pytest.raises(ValidationError) as exc:
        validate_inputs(parse_inputs(raw))
    assert exc.value.field == field


def test_non_finite_value_is_rejected():
    raw = dict(VALID_FORM)
    raw["vcc"] = "nan"
    with pytest.raises(ValidationError) as exc:
        validate_inputs(parse_inputs(raw))
    assert exc.value.field == "vcc"
