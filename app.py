from flask import Flask, render_template, request

from bjt import (
    FIELD_LABELS,
    REGION_LABELS,
    ValidationError,
    analyze,
    parse_inputs,
)

FORM_FIELDS = (
    ("vcc", "แรงดันไฟเลี้ยง VCC", "V"),
    ("r1", "ตัวต้านทาน R1", "Ω"),
    ("r2", "ตัวต้านทาน R2", "Ω"),
    ("rc", "ตัวต้านทาน RC", "Ω"),
    ("re", "ตัวต้านทาน RE", "Ω"),
    ("beta", "อัตราขยายกระแส beta (hFE)", ""),
    ("vbe", "แรงดันเบส-อีมิเตอร์ VBE", "V"),
)

DEFAULT_VALUES = {
    "vcc": "12",
    "r1": "47000",
    "r2": "10000",
    "rc": "2200",
    "re": "1000",
    "beta": "150",
    "vbe": "0.7",
}


def format_result(result) -> list[tuple[str, str, str]]:
    return [
        ("VB", f"{result.vb:.4f}", "V"),
        ("VE", f"{result.ve:.4f}", "V"),
        ("VC", f"{result.vc:.4f}", "V"),
        ("VCE", f"{result.vce:.4f}", "V"),
        ("IB", f"{result.ib * 1e6:.3f}", "µA"),
        ("IC", f"{result.ic * 1e3:.4f}", "mA"),
        ("IE", f"{result.ie * 1e3:.4f}", "mA"),
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


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            fields=FORM_FIELDS,
            values=DEFAULT_VALUES,
            errors={},
        )

    @app.post("/calculate")
    def calculate():
        try:
            inputs = parse_inputs(request.form)
            analysis = analyze(inputs)
        except ValidationError as exc:
            values = {field: request.form.get(field, "") for field in FIELD_LABELS}
            return (
                render_template(
                    "index.html",
                    fields=FORM_FIELDS,
                    values=values,
                    errors={exc.field: exc.message},
                ),
                400,
            )
        return render_template(
            "result.html",
            inputs=inputs,
            analysis=analysis,
            rows=format_result(analysis.primary),
            comparison=comparison_rows(analysis),
            region_labels=REGION_LABELS,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
