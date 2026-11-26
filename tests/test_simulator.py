import shutil

import pytest

import app as app_module
import spice_engine
from app import create_app
from spice_engine import (
    AcResult,
    OpResult,
    SimulationResult,
    SpiceError,
    SpiceUnavailable,
    TranResult,
)

SIM_FORM = {
    "mode": "dc",
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


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_module_app_exposes_all_routes():
    # `flask --app app run` serves the module-level instance, not create_app().
    rules = {rule.rule for rule in app_module.app.url_map.iter_rules()}
    assert {"/", "/simulator", "/calculate", "/simulate"} <= rules


def inputs():
    return spice_engine.parse_form(dict(spice_engine.DEFAULT_FORM))


def make_result(mode="dc", **kwargs):
    return SimulationResult(
        mode=mode,
        inputs=inputs(),
        version="ngspice-47",
        command=(
            r"C:\ngspice\Spice64\bin\ngspice_con.exe",
            "-b",
            "-o",
            "run.log",
            "circuit.cir",
        ),
        log="ngspice-47 batch log\nNo. of Data Rows : 1\n",
        elapsed_s=0.12,
        **kwargs,
    )


def test_get_simulator_lists_reference_fields(client):
    response = client.get("/simulator")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for name in (
        "vcc",
        "r1",
        "r2",
        "rc",
        "re",
        "rl",
        "cin_uf",
        "cout_uf",
        "amp_mv",
        "freq_hz",
        "fstart_hz",
        "fstop_hz",
        "ppd",
        "tstep_us",
        "tstop_ms",
    ):
        assert f'name="{name}"' in body
    assert 'name="bf"' not in body
    assert "BF = 150" in body
    assert 'value="100000"' in body
    assert "ยังไม่ได้รัน" in body


def test_get_simulator_keeps_lab3_navigation(client):
    body = client.get("/simulator").get_data(as_text=True)
    assert "Lab 03" in body
    assert 'href="/"' in body


def test_unknown_mode_on_post_returns_400(client, monkeypatch):
    called = []
    monkeypatch.setattr(
        app_module, "_run_simulation", lambda *args: called.append(args)
    )
    response = client.post("/simulator", data=dict(SIM_FORM, mode="noise"))
    assert response.status_code == 400
    assert "ไม่ถูกต้อง" in response.get_data(as_text=True)
    assert called == []


def test_invalid_re_returns_400_without_running_solver(client, monkeypatch):
    called = []

    def fake_simulate(*args, **kwargs):
        called.append(args)
        return make_result("dc", op=OpResult(2.0, 1.3, 9.0, 7.7, 0.0013))

    monkeypatch.setattr(spice_engine, "simulate", fake_simulate)
    response = client.post("/simulator", data=dict(SIM_FORM, re="0"))
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "มากกว่า 0" in body
    assert 'value="0"' in body
    assert "ngspice สำเร็จ" not in body
    assert called == []


def test_dc_success_renders_spice_and_analytical_provenance(client, monkeypatch):
    op = OpResult(
        vb=2.01301551,
        ve=1.35200569,
        vc=9.04399957,
        vce=7.69199388,
        ic=0.00134412619,
    )
    monkeypatch.setattr(
        app_module, "_run_simulation", lambda *args: make_result("dc", op=op)
    )
    response = client.post("/simulator", data=SIM_FORM)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "ngspice สำเร็จ" in body
    assert "ngspice-47" in body
    assert "2.0130" in body
    assert "7.6920" in body
    assert "1.3441" in body
    assert "Analytical" in body
    assert "dc_bias.py" in body
    assert "SPICE" in body
    # Netlist/BJT model section removed per Lab 04 spec; verify provenance chips remain
    assert "SPICE" in body
    assert "chip-spice" in body


def test_engine_unavailable_returns_503_and_no_success(client, monkeypatch):
    def fail(*args):
        raise SpiceUnavailable("ไม่พบ ngspice ใน PATH")

    monkeypatch.setattr(app_module, "_run_simulation", fail)
    response = client.post("/simulator", data=SIM_FORM)
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    assert "ไม่พบ ngspice" in body
    assert "ngspice สำเร็จ" not in body
    assert "svg class=\"chart\"" not in body


def test_solver_failure_returns_502_and_shows_log(client, monkeypatch):
    def fail(*args):
        raise SpiceError("ngspice รายงานข้อผิดพลาด", log="Error: singular matrix")

    monkeypatch.setattr(app_module, "_run_simulation", fail)
    response = client.post("/simulator", data=SIM_FORM)
    assert response.status_code == 502
    body = response.get_data(as_text=True)
    assert "singular matrix" in body
    assert "ngspice สำเร็จ" not in body


def test_ac_flat_sweep_is_not_given_invented_cutoffs(client, monkeypatch):
    ac = AcResult(
        frequency=(10.0, 1000.0, 1_000_000.0),
        gain_db=(4.9, 4.9, 4.9),
        phase_deg=(180.0, 180.0, 180.0),
    )
    monkeypatch.setattr(
        app_module, "_run_simulation", lambda *args: make_result("ac", ac=ac)
    )
    response = client.post("/simulator", data=dict(SIM_FORM, mode="ac"))
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "AC Frequency Response" in body
    assert "Gain magnitude" in body
    assert "Phase" in body
    assert "Hz" in body
    assert "dB" in body
    assert "180.0°" in body
    assert body.count("not determined in sweep range") == 2
    assert '<svg class="chart"' in body


def test_ac_cutoff_uses_real_crossing_points():
    frequencies = (10.0, 100.0, 1000.0, 10000.0)
    gain = (0.0, 4.0, 10.0, 4.0)
    low, high = app_module._sim_cutoff(frequencies, gain)
    assert low == pytest.approx(10**2.5)
    assert high == pytest.approx(10**3.5)


def test_tran_renders_waveform_units_and_phase_summary(client, monkeypatch):
    tran = TranResult(
        time=(0.0, 0.00025, 0.0005, 0.00075, 0.001),
        vin=(0.0, 0.01, 0.0, -0.01, 0.0),
        vout=(0.0, -0.017, 0.0, 0.017, 0.0),
    )
    monkeypatch.setattr(
        app_module, "_run_simulation", lambda *args: make_result("tran", tran=tran)
    )
    response = client.post("/simulator", data=SIM_FORM)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Transient Response" in body
    assert "10.00 mV" in body
    assert "17.00 mV" in body
    assert "กลับเฟส" in body
    assert "ms" in body
    assert '<svg class="chart"' in body


def test_ac_fields_are_not_required_for_dc_mode(client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_run_simulation",
        lambda *args: make_result(
            "dc",
            op=OpResult(2.0, 1.3, 9.0, 7.7, 0.0013),
        ),
    )
    data = dict(SIM_FORM)
    for field in ("amp_mv", "freq_hz", "fstart_hz", "fstop_hz", "ppd", "tstep_us", "tstop_ms"):
        data[field] = ""
    response = client.post("/simulator", data=data)
    assert response.status_code == 200
    assert "ngspice สำเร็จ" in response.get_data(as_text=True)


NGSPICE_CON = shutil.which("ngspice_con")


@pytest.mark.skipif(not NGSPICE_CON, reason="ngspice_con is not installed on PATH")
def test_real_ngspice_dc_end_to_end(client):
    response = client.post("/simulator", data=SIM_FORM)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "ngspice สำเร็จ" in body
    assert "ngspice-" in body
    assert "2.01" in body
    # BJT model field removed per Lab 04 spec; verify provenance chips remain
    assert "SPICE" in body
    assert "chip-spice" in body
