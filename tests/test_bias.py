import pytest

from bjt import (
    Analysis,
    BiasInputs,
    ValidationError,
    analyze,
    parse_inputs,
    solve_analytic,
    solve_numeric,
    validate_inputs,
)

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


ACTIVE = BiasInputs(vcc=12, r1=47000, r2=10000, rc=2200, re=1000, beta=150, vbe=0.7)


def test_active_operating_point():
    result = solve_analytic(ACTIVE)
    assert result.region == "active"
    assert result.ib == pytest.approx(8.824501487e-06, rel=1e-9)
    assert result.ic == pytest.approx(0.001323675223, rel=1e-9)
    assert result.ie == pytest.approx(0.001332499725, rel=1e-9)
    assert result.vb == pytest.approx(2.032499725, rel=1e-9)
    assert result.ve == pytest.approx(1.332499725, rel=1e-9)
    assert result.vc == pytest.approx(9.087914509, rel=1e-9)
    assert result.vce == pytest.approx(7.755414785, rel=1e-9)
    assert result.warnings == ()


def test_saturation_is_detected():
    inputs = BiasInputs(vcc=12, r1=47000, r2=10000, rc=10000, re=100, beta=300, vbe=0.7)
    result = solve_analytic(inputs)
    assert result.region == "saturation"
    assert result.vce < 0.2
    assert any("saturation" in warning for warning in result.warnings)


def test_cutoff_is_detected():
    inputs = BiasInputs(vcc=12, r1=100000, r2=1000, rc=2200, re=1000, beta=100, vbe=0.7)
    result = solve_analytic(inputs)
    assert result.region == "cutoff"
    assert result.ib == result.ic == result.ie == 0.0
    assert result.ve == 0.0
    assert result.vc == 12.0
    assert result.vce == 12.0
    assert result.vb == pytest.approx(0.1188118812, rel=1e-9)
    assert any("cutoff" in warning for warning in result.warnings)


def test_cutoff_at_exact_boundary():
    inputs = BiasInputs(vcc=12, r1=10000, r2=10000, rc=2200, re=1000, beta=100, vbe=6.0)
    result = solve_analytic(inputs)
    assert result.region == "cutoff"
    assert result.ib == 0.0


def test_high_vbe_relative_to_vcc_is_cutoff():
    inputs = BiasInputs(vcc=12, r1=47000, r2=10000, rc=2200, re=1000, beta=150, vbe=11.9)
    result = solve_analytic(inputs)
    assert result.region == "cutoff"
    assert result.ib == 0.0


SATURATION = BiasInputs(vcc=12, r1=47000, r2=10000, rc=10000, re=100, beta=300, vbe=0.7)
CUTOFF = BiasInputs(vcc=12, r1=100000, r2=1000, rc=2200, re=1000, beta=100, vbe=0.7)


def test_numeric_solver_matches_known_active_values():
    result = solve_numeric(ACTIVE)
    assert result.region == "active"
    assert result.vce == pytest.approx(7.755414785, rel=1e-9)
    assert result.ic == pytest.approx(0.001323675223, rel=1e-9)


@pytest.mark.parametrize("inputs", [ACTIVE, SATURATION, CUTOFF])
def test_methods_agree(inputs):
    analysis = analyze(inputs)
    assert isinstance(analysis, Analysis)
    assert analysis.agrees is True
    assert analysis.max_delta < 1e-9
    assert analysis.primary.region == analysis.independent.region


def test_large_beta_agrees():
    analysis = analyze(
        BiasInputs(vcc=12, r1=47000, r2=10000, rc=2200, re=1000, beta=10000, vbe=0.7)
    )
    assert analysis.agrees is True
    assert analysis.primary.region == "active"
