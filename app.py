from flask import Flask, render_template, request
import dc_bias
from bjt import (
    REGION_LABELS,
    ValidationError,
    analyze,
    parse_inputs,
    validate_inputs,
)
import os
import subprocess
import tempfile
import re
import math
from types import SimpleNamespace

import charts
import spice_engine

app = Flask(__name__)

MODE_LABELS = {
    "dc": "DC Operating Point",
    "ac": "AC Frequency Response",
    "tran": "Transient Response",
}

mode_short = {"dc": "DC", "ac": "AC", "tran": "TRAN"}
mode_tabs = {"dc": "DC Bias", "ac": "AC Sweep", "tran": "Transient"}

# Source group: Amplitude and Frequency (available in all modes)
SOURCE_FIELDS = (
    ("amp_mv", "Amplitude (mV peak)", "mV"),
    ("freq_hz", "Frequency (Hz)", "Hz"),
)

# Form fields definition - used by the simulator template
FORM_FIELDS = {
    "circuit": (
        ("vcc", "VCC (V)", ""),
        ("r1", "R1 (Ω)", ""),
        ("r2", "R2 (Ω)", ""),
        ("rc", "RC (Ω)", ""),
        ("re", "RE (Ω)", ""),
        ("rl", "RL (Ω)", ""),
        ("cin_uf", "Cin (μF)", ""),
        ("cout_uf", "Cout (μF)", ""),
        ("ppd", "PPD", ""),
    ),
    "source": (
        ("amp_mv", "Amplitude (mV peak)", "mV"),
        ("freq_hz", "Frequency (Hz)", "Hz"),
        ("fstart_hz", "Start Frequency (Hz)", "Hz"),
        ("fstop_hz", "Stop Frequency (Hz)", "Hz"),
        ("tstep_us", "Time step (μs)", "μs"),
        ("tstop_ms", "Time stop (ms)", "ms"),
    ),
    "ac": (
        ("amp_mv", "Amplitude (mV peak)", "mV"),
        ("freq_hz", "Frequency (Hz)", "Hz"),
        ("fstart_hz", "Start Frequency (Hz)", "Hz"),
        ("fstop_hz", "Stop Frequency (Hz)", "Hz"),
    ),
    "tran": (
        ("tstep_us", "Time step (μs)", "μs"),
        ("tstop_ms", "Time stop (ms)", "ms"),
    ),
}

# Default form values (baseline fixture)
SIM_FORM = {    "mode": "dc",
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

# Field groups for the Lab 04 form; the badge names the analysis that uses it.
SIM_GROUPS = [
    ("source", "Source", "ALL", SOURCE_FIELDS),
    ("circuit", "Circuit", "ALL", FORM_FIELDS["circuit"]),
    ("ac", "AC sweep", "AC", FORM_FIELDS["ac"]),
    ("tran", "Transient", "TRAN", FORM_FIELDS["tran"]),
]

# Lab 03 analytical DC bias (preserved from the original implementation)
LAB3_MODE_LABELS = {
    "divider": "Voltage Divider Bias",
    "fixed": "Fixed Bias",
    "emitter": "Emitter Bias",
}
LAB3_FORM_FIELDS = {
    "divider": (
        ("vcc", "แรงดันไฟเลี้ยง VCC", "V"),
        ("r1", "ตัวต้านทาน R1", "Ω"),
        ("r2", "ตัวต้านทาน R2", "Ω"),
        ("rc", "ตัวต้านทาน RC", "Ω"),
        ("re", "ตัวต้านทาน RE", "Ω"),
        ("beta", "อัตราขยายกระแส (β)", ""),
        ("vbe", "แรงดันเบส-อีมิเตอร์ VBE", "V"),
    ),
    "fixed": (
        ("vcc", "แรงดันไฟเลี้ยง VCC", "V"),
        ("rb", "ตัวต้านทาน RB", "Ω"),
        ("rc", "ตัวต้านทาน RC", "Ω"),
        ("beta", "อัตราขยายกระแส (β)", ""),
        ("vbe", "แรงดันเบส-อีมิเตอร์ VBE", "V"),
    ),
    "emitter": (
        ("vcc", "แรงดันไฟเลี้ยง VCC", "V"),
        ("rb", "ตัวต้านทาน RB", "Ω"),
        ("rc", "ตัวต้านทาน RC", "Ω"),
        ("re", "ตัวต้านทาน RE", "Ω"),
        ("beta", "อัตราขยายกระแส (β)", ""),
        ("vbe", "แรงดันเบส-อีมิเตอร์ VBE", "V"),
    ),
}
LAB3_MODE_FIELDS = {
    mode: tuple(name for name, _, _ in fields)
    for mode, fields in LAB3_FORM_FIELDS.items()
}
LAB3_DEFAULT_VALUES = {
    "divider": {
        "vcc": "12", "r1": "47000", "r2": "10000", "rc": "2200",
        "re": "1000", "beta": "150", "vbe": "0.7",
    },
    "fixed": {
        "vcc": "12", "rb": "1000000", "rc": "2200", "beta": "100", "vbe": "0.7",
    },
    "emitter": {
        "vcc": "12", "rb": "1000000", "rc": "2200", "re": "1000",
        "beta": "100", "vbe": "0.7",
    },
}


def _format_quantity(raw, unit="", scale=1.0):
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return "—"
    text = f"{number / scale:g}"
    return f"{text} {unit}" if unit else text


def _format_resistance(raw):
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return "—"
    if abs(number) >= 1e6:
        return f"{number / 1e6:g} MΩ"
    if abs(number) >= 1e3:
        return f"{number / 1e3:g} kΩ"
    return f"{number:g} Ω"


def circuit_values(mode, values):
    if mode == "divider":
        return {
            "vcc": _format_quantity(values.get("vcc"), "V"),
            "r1": _format_quantity(values.get("r1"), "kΩ", 1000),
            "r2": _format_quantity(values.get("r2"), "kΩ", 1000),
            "rc": _format_quantity(values.get("rc"), "kΩ", 1000),
            "re": _format_quantity(values.get("re"), "kΩ", 1000),
            "beta": _format_quantity(values.get("beta")),
        }
    circuit = {
        "vcc": _format_quantity(values.get("vcc"), "V"),
        "rb": _format_resistance(values.get("rb")),
        "rc": _format_resistance(values.get("rc")),
        "beta": _format_quantity(values.get("beta")),
    }
    if mode == "emitter":
        circuit["re"] = _format_resistance(values.get("re"))
    return circuit


def format_result(result):
    return [
        ("VB", f"{result['vb_v']:.4f}", "V"),
        ("VE", f"{result['ve_v']:.4f}", "V"),
        ("VC", f"{result['vc_v']:.4f}", "V"),
        ("VCE", f"{result['vce_v']:.4f}", "V"),
        ("IB", f"{result['ib_ua']:.3f}", "µA"),
        ("IC", f"{result['ic_ma']:.4f}", "mA"),
        ("IE", f"{result['ie_ma']:.4f}", "mA"),
    ]


def comparison_rows(analysis):
    quantities = (
        ("VB", "vb", "V", 1.0, 4),
        ("VE", "ve", "V", 1.0, 4),
        ("VC", "vc", "V", 1.0, 4),
        ("VCE", "vce", "V", 1.0, 4),
        ("IB", "ib", "µA", 1e6, 3),
        ("IC", "ic", "mA", 1e3, 4),
        ("IE", "ie", "mA", 1e3, 4),
    )
    rows = []
    for label, attribute, unit, scale, digits in quantities:
        primary = getattr(analysis.primary, attribute) * scale
        independent = getattr(analysis.independent, attribute) * scale
        rows.append({
            "label": label, "unit": unit,
            "primary": f"{primary:.{digits}f}",
            "independent": f"{independent:.{digits}f}",
            "delta": f"{abs(primary - independent):.2e}",
        })
    return rows


def _form_values(mode, form):
    return {field: form.get(field, "") for field in LAB3_MODE_FIELDS[mode]}


def _calculate_lab3(mode, raw):
    if mode == "divider":
        inputs = parse_inputs(raw)
        validate_inputs(inputs)
        analysis = analyze(inputs)
        return dc_bias.divider_result(analysis.primary), analysis
    if mode == "fixed":
        return dc_bias.fixed_bias(**dc_bias.parse_fixed(raw)), None
    if mode == "emitter":
        return dc_bias.emitter_bias(**dc_bias.parse_emitter(raw)), None
    raise ValidationError("mode", f"โหมดไม่ถูกต้อง: {mode}")


# ngspice binary path - adjust as needed
NGSPICE_BIN = r"C:\Users\phich\Tools\ngspice\Spice64\bin\ngspice_con.exe"


class SpiceUnavailable(Exception):
    """Raised when ngspice is not available"""


# The simulator must map the exact exceptions raised by the engine.
SpiceUnavailable = spice_engine.SpiceUnavailable
SpiceError = spice_engine.SpiceError


class OpResult:
    """DC operating point result"""
    def __init__(self, vb, ve, vc, vce, ic):
        self.vb = vb
        self.ve = ve
        self.vc = vc
        self.vce = vce
        self.ic = ic


class AcResult:
    """AC analysis result"""
    def __init__(self, frequency, gain_db, phase_deg):
        self.frequency = frequency
        self.gain_db = gain_db
        self.phase_deg = phase_deg


class TranResult:
    """Transient analysis result"""
    def __init__(self, time, vin, vout):
        self.time = time
        self.vin = vin
        self.vout = vout


def make_result(mode="dc", **kwargs):
    """Create result object from simulation results"""
    if mode == "dc":
        op = kwargs.get("op")
        if op:
            return {
                "op": op,
                "mode": "dc",
                "engine": {
                    "version": "47",
                    "model": "QNPN NPN(IS=1e-14 BF=150 VAF=100)",
                },
            }
    elif mode == "ac":
        ac = kwargs.get("ac")
        if ac:
            return {
                "ac": ac,
                "mode": "ac",
                "engine": {
                    "version": "47",
                    "model": "QNPN NPN(IS=1e-14 BF=150 VAF=100)",
                },
            }
    elif mode == "tran":
        tran = kwargs.get("tran")
        if tran:
            return {
                "tran": tran,
                "mode": "tran",
                "engine": {
                    "version": "47",
                    "model": "QNPN NPN(IS=1e-14 BF=150 VAF=100)",
                },
            }
    return {"mode": mode}


# Module-level _run_simulation that can be monkeypatched by tests
# Tests will patch this function to avoid actually running ngspice
_run_simulation = None


def _run_simulation_default(mode, form_values=None, *args, **kwargs):
    """Run one real ngspice analysis through :mod:`spice_engine`.

    No gain, cutoff or waveform value is produced here: every number returned
    to the UI is parsed by the engine from ``wrdata`` files of this run.
    """

    raw = dict(SIM_FORM)
    raw.update(form_values or kwargs.get("form") or {})
    inputs = spice_engine.parse_form(raw, mode)
    return spice_engine.simulate(mode, inputs)


# Set the default _run_simulation at module level so tests can patch it
_run_simulation = _run_simulation_default


def _sim_cutoff(frequencies, gain):
    """Return log-interpolated (-3 dB) crossings from real sweep points."""
    points = [
        (float(f), float(g))
        for f, g in zip(frequencies, gain)
        if float(f) > 0 and math.isfinite(float(g))
    ]
    if len(points) < 2:
        return None, None

    target = max(g for _, g in points) - 3.0
    low = high = None
    for (f0, g0), (f1, g1) in zip(points, points[1:]):
        if g0 == g1 or (g0 - target) * (g1 - target) > 0:
            continue
        ratio = (target - g0) / (g1 - g0)
        if not 0.0 <= ratio <= 1.0:
            continue
        crossing = 10 ** (
            math.log10(f0) + ratio * (math.log10(f1) - math.log10(f0))
        )
        if g1 > g0:
            low = crossing if low is None else min(low, crossing)
        else:
            high = crossing if high is None else max(high, crossing)
    return low, high


def _view_context(result):
    """Build display-only values from simulation data (no physics here)."""
    ctx = {
        "warnings": tuple(getattr(result, "warnings", ()) or ()),
        "ac_summary": None,
        "ac_rows": [],
        "ac_gain_chart": "",
        "ac_phase_chart": "",
        "ac_low_cutoff": None,
        "ac_high_cutoff": None,
        "ac_sweep": (0, 0),
        "tran_summary": None,
        "tran_chart": "",
        "tran_points": 0,
        "dc_comparison": [],
        "dc_compare_beta": 150.0,
    }
    if result is None:
        return ctx

    op = getattr(result, "op", None)
    inputs = getattr(result, "inputs", None)
    if op is not None and inputs is not None:
        try:
            analytic = analyze(
                parse_inputs(
                    {
                        "vcc": f"{inputs.vcc:g}",
                        "r1": f"{inputs.r1:g}",
                        "r2": f"{inputs.r2:g}",
                        "rc": f"{inputs.rc:g}",
                        "re": f"{inputs.re:g}",
                        "beta": f"{inputs.bf:g}",
                        "vbe": "0.7",
                    }
                )
            ).primary
        except (ValidationError, TypeError, ValueError):
            analytic = None
        if analytic is not None:
            rows = []
            for name, label, unit, scale in (
                ("vb", "VB", "V", 1.0),
                ("ve", "VE", "V", 1.0),
                ("vc", "VC", "V", 1.0),
                ("vce", "VCE", "V", 1.0),
                ("ic", "IC", "mA", 1e3),
            ):
                spice_value = float(getattr(op, name)) * scale
                hand_value = float(getattr(analytic, name)) * scale
                rows.append(
                    SimpleNamespace(
                        label=label,
                        spice=f"{spice_value:.4f}",
                        analytic=f"{hand_value:.4f}",
                        delta=f"{abs(spice_value - hand_value):.2e}",
                        unit=unit,
                    )
                )
            ctx["dc_comparison"] = rows
            ctx["dc_compare_beta"] = float(inputs.bf)

    ac = getattr(result, "ac", None)
    if ac is not None and getattr(ac, "frequency", None):
        freqs = tuple(float(x) for x in ac.frequency)
        gains = tuple(float(x) for x in ac.gain_db)
        phases = tuple(float(x) for x in ac.phase_deg)
        ratios = tuple(10 ** (g / 20.0) for g in gains)
        ref = min(range(len(freqs)), key=lambda i: abs(freqs[i] - 1000.0))
        ctx["ac_summary"] = SimpleNamespace(
            frequency=freqs[ref],
            gain_ratio=ratios[ref],
            gain_db=gains[ref],
            phase=phases[ref],
        )
        ctx["ac_rows"] = [
            SimpleNamespace(f=f, gain_db=g, gain_ratio=r, phase=p)
            for f, g, r, p in zip(freqs, gains, ratios, phases)
        ]
        ctx["ac_gain_chart"] = charts.line_chart(
            [{"name": "|Vout/Vin|", "points": list(zip(freqs, gains))}],
            x_label="Frequency", x_unit="Hz",
            y_label="Gain magnitude", y_unit="dB", log_x=True,
            title="Gain magnitude",
        )
        ctx["ac_phase_chart"] = charts.line_chart(
            [{"name": "Phase", "points": list(zip(freqs, phases))}],
            x_label="Frequency", x_unit="Hz",
            y_label="Phase", y_unit="degrees", log_x=True,
            title="Phase (degrees)",
        )
        ctx["ac_sweep"] = (freqs[0], freqs[-1])
        ctx["ac_low_cutoff"], ctx["ac_high_cutoff"] = _sim_cutoff(freqs, gains)

    tran = getattr(result, "tran", None)
    if tran is not None and getattr(tran, "time", None):
        times = tuple(float(x) for x in tran.time)
        vin = tuple(float(x) for x in tran.vin)
        vout = tuple(float(x) for x in tran.vout)
        vin_peak = max(abs(v) for v in vin)
        vout_peak = max(abs(v) for v in vout)
        peak_i = max(range(len(vin)), key=lambda i: abs(vin[i]))
        inverted = vin[peak_i] * vout[peak_i] < 0
        inputs = getattr(result, "inputs", None)
        freq_hz = float(getattr(inputs, "freq_hz", 1000.0) or 1000.0)
        tstop_s = float(getattr(inputs, "tstop_s", 0.0) or 0.0)
        ctx["tran_summary"] = SimpleNamespace(
            vin_peak=vin_peak,
            vout_peak=vout_peak,
            gain=(vout_peak / vin_peak) if vin_peak else 0.0,
            inverted=inverted,
            cycles=freq_hz * tstop_s,
        )
        ctx["tran_points"] = len(times)
        ctx["tran_chart"] = charts.line_chart(
            [
                {"name": "Vin", "points": [(t * 1e3, v) for t, v in zip(times, vin)]},
                {"name": "Vout", "points": [(t * 1e3, v) for t, v in zip(times, vout)]},
            ],
            x_label="Time", x_unit="ms",
            y_label="Voltage", y_unit="V",
            title="Vin / Vout",
        )
    return ctx


SCHEMATIC_FIELDS = (
    ("vcc", "vcc"),
    ("r1", "r1"),
    ("r2", "r2"),
    ("rc", "rc"),
    ("re", "re"),
    ("rl", "rl"),
    ("cin", "cin_uf"),
    ("cout", "cout_uf"),
    ("bf", "bf"),
)


def schematic_values(defaults, values):
    """Schematic labels follow the values that were actually simulated."""
    circuit = dict(defaults)
    for target, field in SCHEMATIC_FIELDS:
        try:
            circuit[target] = float(values.get(field))
        except (TypeError, ValueError):
            continue
    return circuit


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.config["MODE_LABELS"] = MODE_LABELS
    app.config["MODE_TABS"] = mode_tabs
    app.config["SIM_FORM"] = SIM_FORM
    app.config["NGSPICE_BIN"] = NGSPICE_BIN
    app.config["SHOW_BJT_MODEL"] = False
    app.config["SHOW_RUN_TIME"] = False
    app.config["SHOW_COMMAND"] = False

    # Circuit data for the schematic display
    app.config["CIRCUIT_DEFAULTS"] = {
        "vcc": 12,
        "r1": 100000,
        "r2": 22000,
        "rc": 2200,
        "re": 1000,
        "cin": 10,
        "cout": 10,
        "rl": 10000,
        "bf": 150,
    }

    def render_dashboard(mode, values, errors=None, result=None, analysis=None):
        return render_template(
            "index.html",
            mode=mode,
            mode_labels=LAB3_MODE_LABELS,
            fields=LAB3_FORM_FIELDS[mode],
            values=values,
            errors=errors or {},
            result=result,
            analysis=analysis,
            rows=format_result(result) if result else [],
            comparison=comparison_rows(analysis) if analysis else [],
            circuit=circuit_values(mode, values),
            region_labels=REGION_LABELS,
        )

    # routes
    @app.route("/")
    def index():
        mode = request.args.get("mode", "divider").strip()
        if mode not in LAB3_FORM_FIELDS:
            return render_dashboard(
                "divider", LAB3_DEFAULT_VALUES["divider"],
                errors={"mode": f"โหมดไม่ถูกต้อง: {mode}"},
            ), 400
        result, analysis = _calculate_lab3(mode, LAB3_DEFAULT_VALUES[mode])
        return render_dashboard(mode, LAB3_DEFAULT_VALUES[mode], result=result, analysis=analysis)

    @app.route("/simulator", methods=["GET", "POST"])
    def simulator():
        """Lab 04 CE Amplifier Simulator"""
        from flask import current_app

        if request.method == "GET":
            default_values = current_app.config["SIM_FORM"].copy()
            circuit = current_app.config["CIRCUIT_DEFAULTS"].copy()
            notice = None
            errors = {}
            result = None
            run_status = "idle"
            # Build groups for the template
            groups = SIM_GROUPS
            return render_template(
                "simulator.html",
                mode="dc",
                mode_labels=current_app.config["MODE_LABELS"],
                mode_short=mode_short,
                values=default_values,
                fields=FORM_FIELDS,
                groups=groups,
                notice=notice,
                errors=errors,
                result=result,
                run_status=run_status,
                circuit=circuit,
                show_bjt_model=current_app.config["SHOW_BJT_MODEL"],
                show_run_time=current_app.config["SHOW_RUN_TIME"],
                show_command=current_app.config["SHOW_COMMAND"],
            )

        mode = request.form.get("mode", "dc")
        form_values = dict(request.form)

        # Validate mode
        valid_modes = set(MODE_LABELS.keys())
        if mode not in valid_modes:
            groups = SIM_GROUPS
            return render_template(
                "simulator.html",
                mode=mode,
                mode_labels=MODE_LABELS,
                mode_short=mode_short,
                values=request.form,
                fields=FORM_FIELDS,
                groups=groups,
                notice="โหมดไม่ถูกต้อง",
                errors={"mode": "โหมดไม่ถูกต้อง"},
                result=None,
                run_status="idle",
                circuit=schematic_values(current_app.config["CIRCUIT_DEFAULTS"], form_values),
                show_bjt_model=current_app.config["SHOW_BJT_MODEL"],
                show_run_time=current_app.config["SHOW_RUN_TIME"],
                show_command=current_app.config["SHOW_COMMAND"],
            ), 400

        # Validate inputs
        errors = {}
        try:
            vcc = float(form_values.get("vcc", 12))
            r1 = float(form_values.get("r1", 100000))
            r2 = float(form_values.get("r2", 22000))
            rc = float(form_values.get("rc", 2200))
            re = float(form_values.get("re", 1000))
        except (ValueError, TypeError):
            errors["re"] = "กรุณาป้อนตัวเลข"
            return render_template(
                "simulator.html",
                mode=mode,
                mode_labels=MODE_LABELS,
                mode_short=mode_short,
                values=request.form,
                fields=FORM_FIELDS,
                groups=[
                    ("circuit", "Circuit", "ALL", FORM_FIELDS["circuit"]),
                    ("source", "Source", "TRAN", FORM_FIELDS["source"]),
                    ("ac", "AC sweep", "AC", FORM_FIELDS["ac"]),
                    ("tran", "Transient", "TRAN", FORM_FIELDS["tran"]),
                ],
                notice="กรุณาป้อนตัวเลข",
                errors=errors,
                result=None,
                run_status="idle",
                circuit=schematic_values(current_app.config["CIRCUIT_DEFAULTS"], form_values),
                show_bjt_model=current_app.config["SHOW_BJT_MODEL"],
                show_run_time=current_app.config["SHOW_RUN_TIME"],
                show_command=current_app.config["SHOW_COMMAND"],
            ), 400

        if re <= 0:
            errors["re"] = "RE ต้องมากกว่า 0"
            return render_template(
                "simulator.html",
                mode=mode,
                mode_labels=MODE_LABELS,
                mode_short=mode_short,
                values=request.form,
                fields=FORM_FIELDS,
                groups=[
                    ("circuit", "Circuit", "ALL", FORM_FIELDS["circuit"]),
                    ("source", "Source", "TRAN", FORM_FIELDS["source"]),
                    ("ac", "AC sweep", "AC", FORM_FIELDS["ac"]),
                    ("tran", "Transient", "TRAN", FORM_FIELDS["tran"]),
                ],
                notice="RE ต้องมากกว่า 0",
                errors=errors,
                result=None,
                run_status="idle",
                circuit=schematic_values(current_app.config["CIRCUIT_DEFAULTS"], form_values),
                show_bjt_model=current_app.config["SHOW_BJT_MODEL"],
                show_run_time=current_app.config["SHOW_RUN_TIME"],
                show_command=current_app.config["SHOW_COMMAND"],
            ), 400

        run_status = "idle"
        try:
            result = _run_simulation(mode, form_values)
            notice = None
            error = False
            run_status = "success"
        except spice_engine.SimulationInputError as e:
            return render_template(
                "simulator.html",
                mode=mode,
                mode_labels=MODE_LABELS,
                mode_short=mode_short,
                values=form_values,
                fields=FORM_FIELDS,
                groups=[
                    ("circuit", "Circuit", "ALL", FORM_FIELDS["circuit"]),
                    ("source", "Source", "TRAN", FORM_FIELDS["source"]),
                    ("ac", "AC sweep", "AC", FORM_FIELDS["ac"]),
                    ("tran", "Transient", "TRAN", FORM_FIELDS["tran"]),
                ],
                notice=e.message,
                errors={e.field: e.message},
                result=None,
                run_status="idle",
                circuit=schematic_values(current_app.config["CIRCUIT_DEFAULTS"], form_values),
                show_bjt_model=current_app.config["SHOW_BJT_MODEL"],
                show_run_time=current_app.config["SHOW_RUN_TIME"],
                show_command=current_app.config["SHOW_COMMAND"],
            ), 400
        except SpiceUnavailable as e:
            return render_template(
                "simulator.html",
                mode=mode,
                mode_labels=MODE_LABELS,
                mode_short=mode_short,
                values=form_values,
                fields=FORM_FIELDS,
                groups=[
                    ("circuit", "Circuit", "ALL", FORM_FIELDS["circuit"]),
                    ("source", "Source", "TRAN", FORM_FIELDS["source"]),
                    ("ac", "AC sweep", "AC", FORM_FIELDS["ac"]),
                    ("tran", "Transient", "TRAN", FORM_FIELDS["tran"]),
                ],
                notice=str(e),
                errors={},
                result=None,
                run_status="idle",
                circuit=schematic_values(current_app.config["CIRCUIT_DEFAULTS"], form_values),
                show_bjt_model=current_app.config["SHOW_BJT_MODEL"],
                show_run_time=current_app.config["SHOW_RUN_TIME"],
                show_command=current_app.config["SHOW_COMMAND"],
            ), 503
        except SpiceError as e:
            return render_template(
                "simulator.html",
                mode=mode,
                mode_labels=MODE_LABELS,
                mode_short=mode_short,
                values=form_values,
                fields=FORM_FIELDS,
                groups=[
                    ("circuit", "Circuit", "ALL", FORM_FIELDS["circuit"]),
                    ("source", "Source", "TRAN", FORM_FIELDS["source"]),
                    ("ac", "AC sweep", "AC", FORM_FIELDS["ac"]),
                    ("tran", "Transient", "TRAN", FORM_FIELDS["tran"]),
                ],
                notice=e.message,
                error_log=e.log,
                errors={},
                result=None,
                run_status="idle",
                circuit=schematic_values(current_app.config["CIRCUIT_DEFAULTS"], form_values),
                show_bjt_model=current_app.config["SHOW_BJT_MODEL"],
                show_run_time=current_app.config["SHOW_RUN_TIME"],
                show_command=current_app.config["SHOW_COMMAND"],
            ), 502
        except Exception as e:
            notice = f"Simulation error: {str(e)[:100]}"
            error = True
            result = make_result(mode)
            run_status = "error"

        # Get circuit data for display
        circuit = schematic_values(
            current_app.config["CIRCUIT_DEFAULTS"], form_values
        )

        # Build groups for the template
        groups = SIM_GROUPS

        return render_template(
            "simulator.html",
            mode=mode,
            mode_labels=current_app.config["MODE_LABELS"],
            mode_short=mode_short,
            values=form_values,
            fields=FORM_FIELDS,
            groups=groups,
            notice=notice,
            errors=errors,
            result=result,
            run_status=run_status,
            **_view_context(result),
            circuit=circuit,
            show_bjt_model=current_app.config["SHOW_BJT_MODEL"],
            show_run_time=current_app.config["SHOW_RUN_TIME"],
            show_command=current_app.config["SHOW_COMMAND"],
        )

    @app.route("/calculate", methods=["POST"])
    def calculate():
        """Lab 03 analytical DC bias calculator"""
        mode = (request.form.get("mode") or "divider").strip()
        if mode not in LAB3_FORM_FIELDS:
            return render_dashboard(
                "divider", _form_values("divider", request.form),
                errors={"mode": f"โหมดไม่ถูกต้อง: {mode}"},
            ), 400
        try:
            result, analysis = _calculate_lab3(mode, request.form)
        except ValidationError as exc:
            return render_dashboard(
                mode, _form_values(mode, request.form),
                errors={exc.field: exc.message},
            ), 400
        return render_dashboard(
            mode, _form_values(mode, request.form),
            result=result, analysis=analysis,
        )

    @app.route("/simulate", methods=["POST"])
    def simulate():
        """Alternative simulator route"""
        return simulator()

    return app


# Bind the factory so both `flask --app app run` and `python app.py` serve the
# real routes. Without this the module-level Flask instance has no routes and
# every request returns 404.
app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)