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
