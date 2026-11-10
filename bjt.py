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
    "คำเตือน: วงจรอยู่ในช่วงอิ่มตัว (saturation) — ค่าที่คำนวณได้มาจากสมการช่วง "
    "active จึงไม่ใช่จุดทำงานจริง; VCE จริงใกล้ 0.2 V"
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
