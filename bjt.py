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
