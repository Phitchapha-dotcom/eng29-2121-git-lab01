"""DC bias equations for single-supply Fixed and Emitter bias.

Divider bias keeps using the formulas in :mod:`bjt`; this module only adapts
that result to the shared dictionary shape used by the Flask app.
"""

import math
from typing import Mapping

from bjt import BiasResult, ValidationError

VCE_SAT_V = 0.2

FIELD_LABELS = {
    "vcc": "VCC",
    "rb": "RB",
    "rc": "RC",
    "re": "RE",
    "beta": "beta",
    "vbe": "VBE",
}

FIXED_FIELDS = ("vcc", "rb", "rc", "beta", "vbe")
EMITTER_FIELDS = ("vcc", "rb", "rc", "re", "beta", "vbe")

CUTOFF_MODEL_WARNING = (
    "คำเตือน: IB ≤ 0 — สมการ Forward Active อาจใช้ไม่ได้ "
    "(วงจรอาจอยู่ในช่วง cutoff)"
)
SATURATION_MODEL_WARNING = (
    "คำเตือน: VCE ≤ 0.2 V — สมการ Forward Active อาจใช้ไม่ได้ "
    "(วงจรอาจอยู่ในช่วง saturation); ค่าที่แสดงมาจากสมการ Forward Active"
)


def _parse_required(
    raw: Mapping[str, str], fields: tuple[str, ...]
) -> dict[str, float]:
    values: dict[str, float] = {}
    for field in fields:
        text = (raw.get(field) or "").strip()
        if not text:
            raise ValidationError(field, f"กรุณากรอก {FIELD_LABELS[field]}")
        try:
            values[field] = float(text)
        except ValueError:
            raise ValidationError(
                field, f"{FIELD_LABELS[field]} ต้องเป็นตัวเลข"
            ) from None
    return values


def _validate_common(values: Mapping[str, float]) -> None:
    if not math.isfinite(values["vcc"]) or values["vcc"] <= 0:
        raise ValidationError("vcc", "VCC ต้องเป็นตัวเลขที่มากกว่า 0")
    if not math.isfinite(values["beta"]) or values["beta"] < 1:
        raise ValidationError("beta", "beta ต้องมีค่าอย่างน้อย 1")
    if not math.isfinite(values["vbe"]) or values["vbe"] <= 0:
        raise ValidationError("vbe", "VBE ต้องมากกว่า 0")


def _validate_resistors(
    values: Mapping[str, float], fields: tuple[str, ...]
) -> None:
    for field in fields:
        value = values[field]
        if not math.isfinite(value) or value <= 0:
            raise ValidationError(
                field, f"{FIELD_LABELS[field]} ต้องมากกว่า 0"
            )


def validate_fixed(values: Mapping[str, float]) -> None:
    _validate_common(values)
    _validate_resistors(values, ("rb", "rc"))


def validate_emitter(values: Mapping[str, float]) -> None:
    _validate_common(values)
    _validate_resistors(values, ("rb", "rc", "re"))


def parse_fixed(raw: Mapping[str, str]) -> dict[str, float]:
    values = _parse_required(raw, FIXED_FIELDS)
    validate_fixed(values)
    return values


def parse_emitter(raw: Mapping[str, str]) -> dict[str, float]:
    values = _parse_required(raw, EMITTER_FIELDS)
    validate_emitter(values)
    return values


def _result(
    mode: str,
    *,
    vb: float,
    ve: float,
    vc: float,
    vce: float,
    ib: float,
    ic: float,
    ie: float,
    region: str,
    warnings: tuple[str, ...],
) -> dict:
    return {
        "mode": mode,
        "vb_v": vb,
        "ve_v": ve,
        "vc_v": vc,
        "vce_v": vce,
        "ib_ua": ib * 1e6,
        "ic_ma": ic * 1e3,
        "ie_ma": ie * 1e3,
        "region": region,
        "warnings": warnings,
    }


def _classify(ib: float, vce: float) -> tuple[str, tuple[str, ...]]:
    if ib <= 0:
        return "cutoff", (CUTOFF_MODEL_WARNING,)
    if vce <= VCE_SAT_V:
        return "saturation", (SATURATION_MODEL_WARNING,)
    return "active", ()


def fixed_bias(
    *, vcc: float, rb: float, rc: float, beta: float, vbe: float
) -> dict:
    """Fixed bias: RB from VCC to base, emitter grounded."""
    ib = (vcc - vbe) / rb
    ic = beta * ib
    ie = (beta + 1.0) * ib
    ve = 0.0
    vb = vbe
    vc = vcc - ic * rc
    vce = vc - ve
    region, warnings = _classify(ib, vce)
    return _result(
        "fixed",
        vb=vb,
        ve=ve,
        vc=vc,
        vce=vce,
        ib=ib,
        ic=ic,
        ie=ie,
        region=region,
        warnings=warnings,
    )


def emitter_bias(
    *, vcc: float, rb: float, rc: float, re: float, beta: float, vbe: float
) -> dict:
    """Emitter bias: RB from VCC to base, RE from emitter to ground."""
    ib = (vcc - vbe) / (rb + (beta + 1.0) * re)
    ic = beta * ib
    ie = (beta + 1.0) * ib
    ve = ie * re
    vb = ve + vbe
    vc = vcc - ic * rc
    vce = vc - ve
    region, warnings = _classify(ib, vce)
    return _result(
        "emitter",
        vb=vb,
        ve=ve,
        vc=vc,
        vce=vce,
        ib=ib,
        ic=ic,
        ie=ie,
        region=region,
        warnings=warnings,
    )


def divider_result(result: BiasResult) -> dict:
    """Adapt the unchanged divider result to the shared dictionary shape."""
    return _result(
        "divider",
        vb=result.vb,
        ve=result.ve,
        vc=result.vc,
        vce=result.vce,
        ib=result.ib,
        ic=result.ic,
        ie=result.ie,
        region=result.region,
        warnings=result.warnings,
    )
