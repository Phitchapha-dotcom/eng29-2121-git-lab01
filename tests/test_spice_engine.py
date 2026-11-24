from pathlib import Path

import pytest

import spice_engine
from spice_engine import (
    AcResult,
    CeInputs,
    OpResult,
    SimulationInputError,
    SpiceError,
    SpiceUnavailable,
    TranResult,
    build_netlist,
    parse_form,
    simulate,
)

BASE_FORM = {
    "vcc": "12",
    "r1": "100000",
    "r2": "22000",
    "rc": "2200",
    "re": "1000",
    "rl": "10000",
    "cin_uf": "10",
    "cout_uf": "10",
    "bf": "150",
    "amp_mv": "10",
    "freq_hz": "1000",
    "fstart_hz": "10",
    "fstop_hz": "1000000",
    "ppd": "10",
    "tstep_us": "5",
    "tstop_ms": "5",
}


def form(**overrides):
    data = dict(BASE_FORM)
    data.update(overrides)
    return data


def test_parse_form_builds_baseline_fixture():
    inputs = parse_form(form())
    assert isinstance(inputs, CeInputs)
    assert inputs.vcc == 12
    assert inputs.r1 == 100_000
    assert inputs.r2 == 22_000
    assert inputs.rc == 2200
    assert inputs.re == 1000
    assert inputs.rl == 10_000
    assert inputs.cin_uf == 10
    assert inputs.amp_v == pytest.approx(0.01)
    assert inputs.freq_hz == 1000
    assert "BF=150" in inputs.model
    assert "IS=1e-14" in inputs.model


@pytest.mark.parametrize(
    "field,value",
    [
        ("re", "0"),
        ("re", "-1"),
        ("rc", "0"),
        ("bf", "0"),
        ("vcc", "0"),
        ("cin_uf", "0"),
    ],
)
def test_invalid_component_values_are_rejected(field, value):
    with pytest.raises(SimulationInputError) as exc:
        parse_form(form(**{field: value}))
    assert exc.value.field == field


def test_non_numeric_value_is_rejected_with_field():
    with pytest.raises(SimulationInputError) as exc:
        parse_form(form(r1="100k"))
    assert exc.value.field == "r1"
    assert "ตัวเลข" in exc.value.message


def test_required_field_cannot_be_blank():
    with pytest.raises(SimulationInputError) as exc:
        parse_form(form(re=""))
    assert exc.value.field == "re"
    assert "กรุณากรอก" in exc.value.message


def test_ac_requires_ordered_sweep_and_integer_points():
    with pytest.raises(SimulationInputError) as exc:
        parse_form(form(fstart_hz="1000", fstop_hz="10"), mode="ac")
    assert exc.value.field == "fstop_hz"

    with pytest.raises(SimulationInputError) as exc:
        parse_form(form(ppd="2.5"), mode="ac")
    assert exc.value.field == "ppd"


def test_tran_rejects_more_than_200000_points():
    with pytest.raises(SimulationInputError) as exc:
        parse_form(form(tstep_us="0.001", tstop_ms="1000"), mode="tran")
    assert exc.value.field == "tstep_us"


def test_unknown_analysis_mode_is_rejected():
    with pytest.raises(SimulationInputError) as exc:
        parse_form(form(), mode="noise")
    assert exc.value.field == "analysis"


def test_dc_netlist_contains_reference_components_and_op():
    netlist = build_netlist("dc", parse_form(form()))
    assert ".op" in netlist
    assert "VCC vcc 0 12" in netlist
    assert "R1 vcc base 100000" in netlist
    assert "R2 base 0 22000" in netlist
    assert "RC vcc coll 2200" in netlist
    assert "RE emit 0 1000" in netlist
    assert "CIN in base 1e-05" in netlist
    assert "COUT coll out 1e-05" in netlist
    assert "RL out 0 10000" in netlist
    assert "Q1 coll base emit QNPN" in netlist
    assert "wrdata op.out v(base) v(emit) v(coll) @q1[ic]" in netlist
    assert ".ac" not in netlist
    assert ".tran" not in netlist


def test_ac_and_tran_netlists_use_requested_analyses():
    inputs = parse_form(form(), mode="ac")
    ac = build_netlist("ac", inputs)
    assert ".ac dec 10 10 1000000" in ac
    assert "wrdata ac.out vdb(out) vp(out) vdb(in) vp(in)" in ac

    inputs = parse_form(form(), mode="tran")
    tran = build_netlist("tran", inputs)
    assert ".tran 5e-06 0.005" in tran
    assert "wrdata tran.out v(in) v(out)" in tran
    assert "SIN(0 0.01 1000)" in tran


def test_op_parser_uses_headers_and_computes_vce(tmp_path: Path):
    path = tmp_path / "op.out"
    path.write_text(
        " vcc v(base) v(emit) v(coll) @q1[ic]\n"
        " 12 2.01301551 1.35200569 9.04399957 0.00134412619\n",
        encoding="utf-8",
    )
    op = spice_engine._parse_op(path)
    assert op.vb == pytest.approx(2.01301551)
    assert op.ve == pytest.approx(1.35200569)
    assert op.vc == pytest.approx(9.04399957)
    assert op.ic == pytest.approx(0.00134412619)
    assert op.vce == pytest.approx(9.04399957 - 1.35200569)


def test_ac_parser_converts_phase_radians_to_degrees(tmp_path: Path):
    path = tmp_path / "ac.out"
    path.write_text(
        " frequency vdb(out) vp(out) vdb(in) vp(in)\n"
        " 1000 4.9 3.14159265 0 0\n"
        " 10000 4.8 -3.14159265 0 0\n",
        encoding="utf-8",
    )
    ac = spice_engine._parse_ac(path)
    assert ac.frequency == (1000.0, 10000.0)
    assert ac.gain_db == pytest.approx((4.9, 4.8))
    assert ac.phase_deg == pytest.approx((180.0, -180.0))


def test_tran_parser_reads_time_and_voltages(tmp_path: Path):
    path = tmp_path / "tran.out"
    path.write_text(
        " time v(in) v(out)\n"
        " 0 0 9.04\n"
        " 0.00025 0.01 8.9\n",
        encoding="utf-8",
    )
    tran = spice_engine._parse_tran(path)
    assert tran.time == (0.0, 0.00025)
    assert tran.vin == (0.0, 0.01)
    assert tran.vout == (9.04, 8.9)


def test_missing_wrdata_file_raises_spice_error(tmp_path: Path):
    with pytest.raises(SpiceError):
        spice_engine._parse_op(tmp_path / "missing.out")


def test_empty_wrdata_file_raises_spice_error(tmp_path: Path):
    path = tmp_path / "empty.out"
    path.write_text("", encoding="utf-8")
    with pytest.raises(SpiceError):
        spice_engine._parse_op(path)


def test_missing_binary_raises_unavailable(monkeypatch):
    monkeypatch.setattr(spice_engine, "ngspice_binary", lambda: "no-such-ngspice-xyz")
    with pytest.raises(SpiceUnavailable):
        simulate("dc", parse_form(form()))


def test_timeout_is_reported_as_spice_error(monkeypatch):
    monkeypatch.setattr(spice_engine, "ngspice_binary", lambda: "ngspice_con")

    def fake_run(*args, **kwargs):
        raise spice_engine.subprocess.TimeoutExpired(cmd="ngspice_con", timeout=30)

    monkeypatch.setattr(spice_engine.subprocess, "run", fake_run)
    with pytest.raises(SpiceError) as exc:
        simulate("dc", parse_form(form()))
    assert "เวลาเกิน" in exc.value.message


def test_success_without_output_file_is_not_treated_as_success(monkeypatch):
    monkeypatch.setattr(spice_engine, "ngspice_binary", lambda: "ngspice_con")

    class FakeProcess:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(
        spice_engine.subprocess, "run", lambda *args, **kwargs: FakeProcess()
    )
    with pytest.raises(SpiceError) as exc:
        simulate("dc", parse_form(form()))
    assert "ไม่พบไฟล์ผลลัพธ์" in exc.value.message


def test_nonzero_exit_is_reported(monkeypatch):
    monkeypatch.setattr(spice_engine, "ngspice_binary", lambda: "ngspice_con")

    class FakeProcess:
        returncode = 1
        stdout = ""
        stderr = "singular matrix"

    monkeypatch.setattr(
        spice_engine.subprocess, "run", lambda *args, **kwargs: FakeProcess()
    )
    with pytest.raises(SpiceError) as exc:
        simulate("dc", parse_form(form()))
    assert "รหัส 1" in exc.value.message


def test_command_uses_argument_list_without_shell(tmp_path):
    """The netlist runner must never opt into a shell or interpolate form text."""
    source = Path(spice_engine.__file__).read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert "subprocess.run(" in source
    assert "timeout=timeout" in source
