from flask import Flask, render_template, request

import dc_bias
from bjt import (
    REGION_LABELS,
    ValidationError,
    analyze,
    parse_inputs,
    validate_inputs,
)

MODE_LABELS = {
    "divider": "Voltage Divider Bias",
    "fixed": "Fixed Bias",
    "emitter": "Emitter Bias",
}

FORM_FIELDS = {
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

MODE_FIELDS = {
    mode: tuple(name for name, _, _ in fields)
    for mode, fields in FORM_FIELDS.items()
}

DEFAULT_VALUES = {
    "divider": {
        "vcc": "12",
        "r1": "47000",
        "r2": "10000",
        "rc": "2200",
        "re": "1000",
        "beta": "150",
        "vbe": "0.7",
    },
    "fixed": {
        "vcc": "12",
        "rb": "1000000",
        "rc": "2200",
        "beta": "100",
        "vbe": "0.7",
    },
    "emitter": {
        "vcc": "12",
        "rb": "1000000",
        "rc": "2200",
        "re": "1000",
        "beta": "100",
        "vbe": "0.7",
    },
}


def _format_quantity(raw, unit: str = "", scale: float = 1.0) -> str:
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return "—"
    text = f"{number / scale:g}"
    return f"{text} {unit}" if unit else text


def _format_resistance(raw) -> str:
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return "—"
    if abs(number) >= 1e6:
        return f"{number / 1e6:g} MΩ"
    if abs(number) >= 1e3:
        return f"{number / 1e3:g} kΩ"
    return f"{number:g} Ω"


def circuit_values(mode: str, values) -> dict[str, str]:
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


def format_result(result) -> list[tuple[str, str, str]]:
    return [
        ("VB", f"{result['vb_v']:.4f}", "V"),
        ("VE", f"{result['ve_v']:.4f}", "V"),
        ("VC", f"{result['vc_v']:.4f}", "V"),
        ("VCE", f"{result['vce_v']:.4f}", "V"),
        ("IB", f"{result['ib_ua']:.3f}", "µA"),
        ("IC", f"{result['ic_ma']:.4f}", "mA"),
        ("IE", f"{result['ie_ma']:.4f}", "mA"),
    ]


def comparison_rows(analysis) -> list[dict[str, str]]:
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
        rows.append(
            {
                "label": label,
                "unit": unit,
                "primary": f"{primary:.{digits}f}",
                "independent": f"{independent:.{digits}f}",
                "delta": f"{abs(primary - independent):.2e}",
            }
        )
    return rows


def _form_values(mode: str, form) -> dict[str, str]:
    return {field: form.get(field, "") for field in MODE_FIELDS[mode]}


def _calculate(mode: str, raw):
    if mode == "divider":
        inputs = parse_inputs(raw)
        validate_inputs(inputs)
        analysis = analyze(inputs)
        return dc_bias.divider_result(analysis.primary), analysis
    elif mode == "fixed":
        values = dc_bias.parse_fixed(raw)
        return dc_bias.fixed_bias(**values), None
    elif mode == "emitter":
        values = dc_bias.parse_emitter(raw)
        return dc_bias.emitter_bias(**values), None
    else:
        raise ValidationError("mode", f"โหมดไม่ถูกต้อง: {mode}")


def create_app() -> Flask:
    app = Flask(__name__)

    def render_dashboard(mode, values, errors=None, result=None, analysis=None):
        return render_template(
            "index.html",
            mode=mode,
            mode_labels=MODE_LABELS,
            fields=FORM_FIELDS[mode],
            values=values,
            errors=errors or {},
            result=result,
            analysis=analysis,
            rows=format_result(result) if result else [],
            comparison=comparison_rows(analysis) if analysis else [],
            circuit=circuit_values(mode, values),
            region_labels=REGION_LABELS,
        )

    @app.get("/")
    def index():
        mode = request.args.get("mode", "divider").strip()
        if mode not in FORM_FIELDS:
            return render_dashboard(
                "divider",
                DEFAULT_VALUES["divider"],
                errors={"mode": f"โหมดไม่ถูกต้อง: {mode}"},
            ), 400
        values = DEFAULT_VALUES[mode]
        result, analysis = _calculate(mode, values)
        return render_dashboard(mode, values, result=result, analysis=analysis)

    @app.post("/calculate")
    def calculate():
        mode = (request.form.get("mode") or "divider").strip()
        if mode not in FORM_FIELDS:
            return render_dashboard(
                "divider",
                _form_values("divider", request.form),
                errors={"mode": f"โหมดไม่ถูกต้อง: {mode}"},
            ), 400
        try:
            result, analysis = _calculate(mode, request.form)
        except ValidationError as exc:
            return render_dashboard(
                mode,
                _form_values(mode, request.form),
                errors={exc.field: exc.message},
            ), 400
        return render_dashboard(
            mode,
            _form_values(mode, request.form),
            result=result,
            analysis=analysis,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
