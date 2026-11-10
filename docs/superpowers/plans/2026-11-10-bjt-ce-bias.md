# BJT Common-Emitter DC Bias Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal Flask app that computes the DC operating point of a voltage-divider-biased NPN common-emitter stage, validates input, warns about cutoff/saturation, and cross-checks the result with an independent nodal solve.

**Architecture:** `bjt.py` holds pure engineering logic (parsing, validation, analytic solve, numeric solve, comparison) with no Flask imports. `app.py` is a Flask app factory with two routes that call `bjt.py`. Jinja templates and one plain CSS file render the form and result. pytest covers logic and routes.

**Tech Stack:** Python 3.12, Flask 3.x, pytest 8.x. Pure Python only — no NumPy/SciPy, no JavaScript.

**Spec:** `docs/superpowers/specs/2026-11-10-bjt-ce-bias-design.md`

## Global Constraints

- Python 3.12; `Flask>=3.0,<4`; `pytest>=8,<9`.
- No NumPy, SciPy, JavaScript framework, database, or auth.
- Do not modify `electrical.py` or `test_electrical.py`.
- `VCE_SAT_V = 0.2` (volts).
- Cross-check tolerance: `math.isclose(rel_tol=1e-9, abs_tol=1e-9)`.
- Display voltages in V (4 decimals), `IB` in µA (3 decimals), `IC`/`IE` in mA (4 decimals).
- UI labels and messages in Thai; engineering terms and unit symbols in English.
- Validation: `VCC > 0`; `R1, R2, RC, RE > 0`; `beta >= 1`; `0 < VBE < VCC`; all values finite.
- Cutoff when `VBB <= VBE`; saturation when `VCE < VCE_SAT_V`; otherwise active.
- Work on branch `feature/bjt-ce-bias` in a worktree; one commit per task.
- Route behavior: invalid `POST /calculate` returns HTTP 400 and re-renders the form with submitted values preserved.

## Review Focus

1. **`VBB` exactly equal to `VBE`** must be cutoff, not active — test in Task 2.
2. **Very large `beta` (10000)** must not break agreement or formatting — test in Task 3.
3. **`VBE` close to `VCC` (e.g. 11.9 of 12)** must report cutoff, not negative currents or a crash — test in Task 2.
4. **Values like `47,000` or ` 12 `** must produce a clear Thai error with the input preserved, not a 500 — test in Task 4.
5. **Empty or missing form field** must produce HTTP 400, not a traceback — test in Task 4.

---

### Task 1: Scaffold, parsing, and validation

**Files:**
- Create: `requirements.txt`
- Modify: `.gitignore`
- Create: `bjt.py`
- Create: `tests/test_bias.py`

**Interfaces:**
- Produces: `VCE_SAT_V: float`, `FIELD_LABELS: dict[str, str]`, `REGION_LABELS: dict[str, str]`, `class ValidationError(ValueError)` with attributes `field: str` and `message: str`, `@dataclass(frozen=True) class BiasInputs` with fields `vcc, r1, r2, rc, re, beta, vbe: float`, `parse_inputs(raw: Mapping[str, str]) -> BiasInputs`, `validate_inputs(inputs: BiasInputs) -> None`.

- [ ] **Step 1: Create the virtual environment and dependency file**

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install "Flask>=3.0,<4" "pytest>=8,<9"
```

Write `requirements.txt`:

```
Flask>=3.0,<4
pytest>=8,<9
```

Append to `.gitignore` (keep existing lines):

```
.venv/
__pycache__/
.pytest_cache/
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_bias.py` with exactly these tests (add `import math` only when a later task needs it):

```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_bias.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bjt'`.

- [ ] **Step 4: Implement the data types, parsing, and validation in `bjt.py`**

Create `bjt.py` with:

```python
import math
from dataclasses import dataclass
from typing import Mapping

VCE_SAT_V = 0.2

FIELD_LABELS = {
    "vcc": "VCC",
    "r1": "R1",
    "r2": "R2",
    "rc": "RC",
    "re": "RE",
    "beta": "beta",
    "vbe": "VBE",
}

REGION_LABELS = {
    "active": "Active (ใช้งานปกติ)",
    "saturation": "Saturation (อิ่มตัว)",
    "cutoff": "Cutoff (ตัดการทำงาน)",
}


class ValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class BiasInputs:
    vcc: float
    r1: float
    r2: float
    rc: float
    re: float
    beta: float
    vbe: float


def parse_inputs(raw: Mapping[str, str]) -> BiasInputs:
    values = {}
    for field in FIELD_LABELS:
        text = (raw.get(field) or "").strip()
        if not text:
            raise ValidationError(field, f"กรุณากรอก {FIELD_LABELS[field]}")
        try:
            values[field] = float(text)
        except ValueError:
            raise ValidationError(
                field, f"{FIELD_LABELS[field]} ต้องเป็นตัวเลข"
            ) from None
    return BiasInputs(**values)


def validate_inputs(inputs: BiasInputs) -> None:
    if not math.isfinite(inputs.vcc) or inputs.vcc <= 0:
        raise ValidationError("vcc", "VCC ต้องเป็นตัวเลขที่มากกว่า 0")
    for field in ("r1", "r2", "rc", "re"):
        value = getattr(inputs, field)
        if not math.isfinite(value) or value <= 0:
            raise ValidationError(field, f"{FIELD_LABELS[field]} ต้องมากกว่า 0")
    if not math.isfinite(inputs.beta) or inputs.beta < 1:
        raise ValidationError("beta", "beta ต้องมีค่าอย่างน้อย 1")
    if not math.isfinite(inputs.vbe) or inputs.vbe <= 0:
        raise ValidationError("vbe", "VBE ต้องมากกว่า 0")
    if inputs.vbe >= inputs.vcc:
        raise ValidationError("vbe", "VBE ต้องน้อยกว่า VCC")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_bias.py -v`
Expected: PASS (25 tests).

- [ ] **Step 6: Commit**

```bash
git add .gitignore requirements.txt bjt.py tests/test_bias.py
git commit -m "feat: add BJT input parsing and validation"
```

---

### Task 2: Analytic DC operating point

**Files:**
- Modify: `bjt.py`
- Modify: `tests/test_bias.py`

**Interfaces:**
- Consumes: `BiasInputs`, `ValidationError`, `VCE_SAT_V`, `REGION_LABELS`.
- Produces: `@dataclass(frozen=True) class BiasResult` with fields `vb, ve, vc, vce, ib, ic, ie: float`, `region: str`, `warnings: tuple[str, ...]`; `solve_analytic(inputs: BiasInputs) -> BiasResult`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bias.py`:

```python
from bjt import BiasResult, solve_analytic

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_bias.py -v`
Expected: FAIL with `ImportError: cannot import name 'BiasResult'`.

- [ ] **Step 3: Implement `BiasResult` and `solve_analytic` in `bjt.py`**

Add below `BiasInputs`:

```python
@dataclass(frozen=True)
class BiasResult:
    vb: float
    ve: float
    vc: float
    vce: float
    ib: float
    ic: float
    ie: float
    region: str
    warnings: tuple[str, ...]


CUTOFF_WARNING = (
    "คำเตือน: ทรานซิสเตอร์อยู่ในช่วงตัดการทำงาน (cutoff) — "
    "VBB ไม่มากพอที่จะไบอัสเบส-อีมิเตอร์"
)
SATURATION_WARNING = (
    "คำเตือน: วงจรอยู่ในช่วงอิ่มตัว (saturation) — VCE ต่ำกว่า 0.2 V "
    "สมการช่วง active ไม่แม่นยำ"
)


def _base_divider(inputs: BiasInputs) -> tuple[float, float]:
    vbb = inputs.vcc * inputs.r2 / (inputs.r1 + inputs.r2)
    rb = inputs.r1 * inputs.r2 / (inputs.r1 + inputs.r2)
    return vbb, rb


def _make_result(
    inputs: BiasInputs,
    *,
    vb: float,
    ve: float,
    vc: float,
    vce: float,
    ib: float,
    ic: float,
    ie: float,
) -> BiasResult:
    vbb, _ = _base_divider(inputs)
    if vbb <= inputs.vbe:
        return BiasResult(
            vb=vbb,
            ve=0.0,
            vc=inputs.vcc,
            vce=inputs.vcc,
            ib=0.0,
            ic=0.0,
            ie=0.0,
            region="cutoff",
            warnings=(CUTOFF_WARNING,),
        )
    if vce < VCE_SAT_V:
        return BiasResult(
            vb=vb,
            ve=ve,
            vc=vc,
            vce=vce,
            ib=ib,
            ic=ic,
            ie=ie,
            region="saturation",
            warnings=(SATURATION_WARNING,),
        )
    return BiasResult(
        vb=vb,
        ve=ve,
        vc=vc,
        vce=vce,
        ib=ib,
        ic=ic,
        ie=ie,
        region="active",
        warnings=(),
    )


def solve_analytic(inputs: BiasInputs) -> BiasResult:
    vbb, rb = _base_divider(inputs)
    ib = (vbb - inputs.vbe) / (rb + (inputs.beta + 1) * inputs.re)
    ic = inputs.beta * ib
    ie = (inputs.beta + 1) * ib
    ve = ie * inputs.re
    vb = ve + inputs.vbe
    vc = inputs.vcc - ic * inputs.rc
    return _make_result(
        inputs, vb=vb, ve=ve, vc=vc, vce=vc - ve, ib=ib, ic=ic, ie=ie
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_bias.py -v`
Expected: PASS (30 tests).

- [ ] **Step 5: Commit**

```bash
git add bjt.py tests/test_bias.py
git commit -m "feat: add analytic BJT bias solver"
```

---

### Task 3: Independent numeric solve and comparison

**Files:**
- Modify: `bjt.py`
- Modify: `tests/test_bias.py`

**Interfaces:**
- Consumes: `BiasInputs`, `BiasResult`, `solve_analytic`.
- Produces: `@dataclass(frozen=True) class Analysis` with fields `primary: BiasResult`, `independent: BiasResult`, `max_delta: float`, `agrees: bool`; `solve_numeric(inputs: BiasInputs) -> BiasResult`; `analyze(inputs: BiasInputs) -> Analysis`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bias.py`:

```python
from bjt import Analysis, analyze, solve_numeric

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
    analysis = analyze(BiasInputs(vcc=12, r1=47000, r2=10000, rc=2200, re=1000, beta=10000, vbe=0.7))
    assert analysis.agrees is True
    assert analysis.primary.region == "active"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_bias.py -v`
Expected: FAIL with `ImportError: cannot import name 'Analysis'`.

- [ ] **Step 3: Implement the numeric solver and comparison in `bjt.py`**

Add at the end of `bjt.py`:

```python
@dataclass(frozen=True)
class Analysis:
    primary: BiasResult
    independent: BiasResult
    max_delta: float
    agrees: bool


def _solve_3x3(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    a = [row[:] + [value] for row, value in zip(matrix, rhs)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(a[row][column]))
        if a[pivot][column] == 0:
            raise ValueError("Singular circuit matrix.")
        a[column], a[pivot] = a[pivot], a[column]
        for row in range(column + 1, 3):
            factor = a[row][column] / a[column][column]
            for index in range(column, 4):
                a[row][index] -= factor * a[column][index]
    solution = [0.0, 0.0, 0.0]
    for row in range(2, -1, -1):
        total = a[row][3] - sum(
            a[row][column] * solution[column] for column in range(row + 1, 3)
        )
        solution[row] = total / a[row][row]
    return solution


def solve_numeric(inputs: BiasInputs) -> BiasResult:
    beta_plus_one_re = (inputs.beta + 1) * inputs.re
    matrix = [
        [1 / inputs.r1 + 1 / inputs.r2, 1 / beta_plus_one_re, 0.0],
        [1.0, -1.0, 0.0],
        [0.0, inputs.beta / beta_plus_one_re, 1 / inputs.rc],
    ]
    rhs = [inputs.vcc / inputs.r1, inputs.vbe, inputs.vcc / inputs.rc]
    vb, ve, vc = _solve_3x3(matrix, rhs)
    ib = ve / beta_plus_one_re
    ic = inputs.beta * ib
    ie = (inputs.beta + 1) * ib
    return _make_result(
        inputs, vb=vb, ve=ve, vc=vc, vce=vc - ve, ib=ib, ic=ic, ie=ie
    )


def analyze(inputs: BiasInputs) -> Analysis:
    validate_inputs(inputs)
    primary = solve_analytic(inputs)
    independent = solve_numeric(inputs)
    quantities = ("vb", "ve", "vc", "vce", "ib", "ic", "ie")
    deltas = [
        abs(getattr(primary, name) - getattr(independent, name))
        for name in quantities
    ]
    agrees = all(
        math.isclose(
            getattr(primary, name),
            getattr(independent, name),
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
        for name in quantities
    )
    return Analysis(
        primary=primary,
        independent=independent,
        max_delta=max(deltas),
        agrees=agrees,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_bias.py -v`
Expected: PASS (35 tests).

- [ ] **Step 5: Commit**

```bash
git add bjt.py tests/test_bias.py
git commit -m "feat: add independent nodal solver and cross-check"
```

---

### Task 4: Flask routes, form, and basic result page

**Files:**
- Create: `app.py`
- Create: `templates/base.html`
- Create: `templates/index.html`
- Create: `templates/result.html`
- Create: `static/style.css`
- Create: `tests/test_app.py`

**Interfaces:**
- Consumes: `parse_inputs`, `analyze`, `ValidationError`, `FIELD_LABELS`, `REGION_LABELS` from `bjt.py`.
- Produces: `create_app() -> Flask`, module-level `app`, `FORM_FIELDS: tuple[tuple[str, str, str], ...]`, `DEFAULT_VALUES: dict[str, str]`, `RESULT_ROWS` formatting helper `format_result(result: BiasResult) -> list[tuple[str, str, str]]`, and `comparison_rows(analysis) -> list[dict]` (used in Task 5).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app.py`:

```python
import pytest

from app import create_app

VALID_FORM = {
    "vcc": "12",
    "r1": "47000",
    "r2": "10000",
    "rc": "2200",
    "re": "1000",
    "beta": "150",
    "vbe": "0.7",
}


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_form_page_lists_all_fields(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for name in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
        assert f'name="{name}"' in body


def test_valid_submission_shows_operating_point(client):
    response = client.post("/calculate", data=VALID_FORM)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "7.7554" in body
    assert "Active" in body


def test_invalid_submission_returns_400_and_keeps_values(client):
    response = client.post("/calculate", data=dict(VALID_FORM, r1="0"))
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "มากกว่า 0" in body
    assert 'value="0"' in body


def test_missing_field_returns_400(client):
    data = {key: value for key, value in VALID_FORM.items() if key != "vcc"}
    response = client.post("/calculate", data=data)
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "กรุณากรอก VCC" in body


def test_non_numeric_value_returns_400(client):
    response = client.post("/calculate", data=dict(VALID_FORM, r1="47,000"))
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "ต้องเป็นตัวเลข" in body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Implement `app.py`**

```python
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
            region_labels=REGION_LABELS,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
```

- [ ] **Step 4: Create the templates and CSS**

`templates/base.html`:

```html
<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BJT Common-Emitter DC Bias</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
  <main>
    <h1>BJT Common-Emitter DC Bias</h1>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

`templates/index.html`:

```html
{% extends "base.html" %}
{% block content %}
<form method="post" action="{{ url_for('calculate') }}">
  {% for name, label, unit in fields %}
  <div class="field">
    <label for="{{ name }}">{{ label }}{% if unit %} ({{ unit }}){% endif %}</label>
    <input id="{{ name }}" name="{{ name }}" type="number" step="any" value="{{ values[name] }}">
    {% if errors.get(name) %}<p class="error">{{ errors[name] }}</p>{% endif %}
  </div>
  {% endfor %}
  <button type="submit">คำนวณ</button>
</form>
{% endblock %}
```

`templates/result.html`:

```html
{% extends "base.html" %}
{% block content %}
<section class="region region-{{ analysis.primary.region }}">
  <strong>{{ region_labels[analysis.primary.region] }}</strong>
</section>

{% for warning in analysis.primary.warnings %}
<p class="warning">{{ warning }}</p>
{% endfor %}

<table>
  <thead>
    <tr><th>ค่า</th><th>ผลลัพธ์</th><th>หน่วย</th></tr>
  </thead>
  <tbody>
    {% for label, value, unit in rows %}
    <tr><td>{{ label }}</td><td>{{ value }}</td><td>{{ unit }}</td></tr>
    {% endfor %}
  </tbody>
</table>

<p><a href="{{ url_for('index') }}">คำนวณใหม่</a></p>
{% endblock %}
```

`static/style.css`:

```css
body {
  font-family: system-ui, sans-serif;
  margin: 0;
  background: #f6f7f9;
  color: #1d2430;
}
main {
  max-width: 760px;
  margin: 2rem auto;
  padding: 1.5rem;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}
.field { margin-bottom: 0.9rem; }
label { display: block; font-weight: 600; margin-bottom: 0.25rem; }
input { width: 100%; padding: 0.45rem; box-sizing: border-box; }
button { padding: 0.6rem 1.2rem; font-weight: 600; cursor: pointer; }
.error { color: #b42318; margin: 0.25rem 0 0; }
.warning { color: #92400e; background: #fef3c7; padding: 0.6rem; border-radius: 6px; }
.region { padding: 0.6rem; border-radius: 6px; margin-bottom: 1rem; }
.region-active { background: #dcfce7; }
.region-saturation, .region-cutoff { background: #fee2e2; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
th, td { text-align: left; padding: 0.45rem; border-bottom: 1px solid #e5e7eb; }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_app.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add app.py templates static tests/test_app.py
git commit -m "feat: add Flask form and operating-point result page"
```

---

### Task 5: Comparison table and result styling

**Files:**
- Modify: `templates/result.html`
- Modify: `static/style.css`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `comparison_rows(analysis)` from `app.py`; `analysis.agrees`, `analysis.max_delta`.
- Produces: comparison section in the result page; no new Python API.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app.py`:

```python
def test_result_page_shows_independent_comparison(client):
    response = client.post("/calculate", data=VALID_FORM)
    body = response.get_data(as_text=True)
    assert "Independent" in body
    assert "ผ่าน" in body
    assert "µA" in body


def test_saturation_warning_is_shown(client):
    response = client.post(
        "/calculate",
        data=dict(VALID_FORM, rc="10000", re="100", beta="300"),
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Saturation" in body
    assert "คำเตือน" in body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_app.py -v`
Expected: FAIL because the result page has no `Independent` text.

- [ ] **Step 3: Add the comparison section to `templates/result.html`**

Insert after the operating-point table and before the "คำนวณใหม่" link:

```html
<h2>ตรวจทานด้วยวิธีอิสระ (Independent check)</h2>
<p class="badge {% if analysis.agrees %}badge-pass{% else %}badge-fail{% endif %}">
  {% if analysis.agrees %}ผ่าน{% else %}ไม่ผ่าน{% endif %}
  (ผลต่างสูงสุด {{ "%.2e"|format(analysis.max_delta) }})
</p>
<table>
  <thead>
    <tr><th>ค่า</th><th>Analytic</th><th>Independent</th><th>ผลต่าง</th><th>หน่วย</th></tr>
  </thead>
  <tbody>
    {% for row in comparison %}
    <tr>
      <td>{{ row.label }}</td>
      <td>{{ row.primary }}</td>
      <td>{{ row.independent }}</td>
      <td>{{ row.delta }}</td>
      <td>{{ row.unit }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
```

Update the `calculate` route in `app.py` to pass `comparison=comparison_rows(analysis)` to `render_template`.

- [ ] **Step 4: Add badge styles to `static/style.css`**

```css
.badge { display: inline-block; padding: 0.35rem 0.7rem; border-radius: 999px; font-weight: 700; }
.badge-pass { background: #dcfce7; color: #166534; }
.badge-fail { background: #fee2e2; color: #991b1b; }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_app.py -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add app.py templates/result.html static/style.css tests/test_app.py
git commit -m "feat: show independent comparison and pass/fail badge"
```

---

### Task 6: README, full suite, and localhost smoke test

**Files:**
- Modify: `README.md`
- Verify: all files

**Interfaces:**
- Consumes: everything above.
- Produces: run instructions and a verified localhost demo.

- [ ] **Step 1: Add the README section**

Append to `README.md`:

```markdown
## BJT Common-Emitter DC Bias Web App

แอป Flask สำหรับคำนวณจุดทำงาน DC ของวงจรไบอัส BJT แบบ common-emitter
(วงจรแบ่งแรงดัน) พร้อมตรวจสอบข้อมูล นำเข้า เตือนช่วง cutoff/saturation และ
ตรวจทานผลด้วยวิธี nodal ที่เป็นอิสระ

### วิธีรัน

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

เปิด http://127.0.0.1:5000

### วิธีทดสอบ

```powershell
.venv\Scripts\python -m pytest -q
```
```

- [ ] **Step 2: Run the full test suite**

Run: `.venv\Scripts\python -m pytest -q`
Expected: all tests pass (42 tests), no failures.

- [ ] **Step 3: Smoke-test the running app**

Start the server in the background:

```powershell
.venv\Scripts\python app.py
```

Then verify with the Flask test client (or a browser at `http://127.0.0.1:5000`):

```powershell
.venv\Scripts\python -c "from app import create_app; c=create_app().test_client(); print(c.get('/').status_code); print(c.post('/calculate', data={'vcc':'12','r1':'47000','r2':'10000','rc':'2200','re':'1000','beta':'150','vbe':'0.7'}).status_code)"
```

Expected: `200` then `200`, and the page shows `VCE = 7.7554 V`, region `Active`, and `ผ่าน`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document BJT web app usage"
```

---

## Self-Review

- **Spec coverage:** layout (Task 1, 4), analytic model (Task 2), independent model and comparison (Task 3, 5), validation (Task 1, 4), region warnings (Task 2), routes/UI (Task 4, 5), tests (Tasks 1–5), run/git (Task 6).
- **Placeholders:** none; every task names exact files, signatures, values, and commands.
- **Type consistency:** `BiasInputs`, `BiasResult`, `Analysis`, `ValidationError.field`, `solve_analytic`, `solve_numeric`, `analyze`, `format_result`, `comparison_rows` are used consistently.
- **Review Focus:** each of the five risks has a test in the owning task (Tasks 2, 3, 4).
