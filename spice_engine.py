"""ngspice adapter for the reference CE voltage-divider amplifier (Lab 04).

The module is intentionally independent from Flask: it validates simulator
inputs, writes a netlist, runs the external ``ngspice`` batch executable with
``subprocess.run`` (argument list, no shell), and parses the ASCII files written
by ``wrdata``.  Every number surfaced to the UI comes from those files.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

MODEL_NAME = "QNPN"
MODEL_IS = 1e-14
MODEL_VAF = 100.0
DEFAULT_TIMEOUT_S = 30.0
ANALYSIS_MODES = ("dc", "ac", "tran")

FIELD_LABELS = {
    "vcc": "VCC",
    "r1": "R1",
    "r2": "R2",
    "rc": "RC",
    "re": "RE",
    "rl": "RL",
    "cin_uf": "CIN",
    "cout_uf": "COUT",
    "bf": "BF",
    "amp_mv": "Amplitude",
    "freq_hz": "Frequency",
    "fstart_hz": "f_start",
    "fstop_hz": "f_stop",
    "ppd": "Points/decade",
    "tstep_us": "Time step",
    "tstop_ms": "Stop time",
}

# Values are in the units shown on the form: V, ohm, uF, mV, Hz, us, ms.
DEFAULT_FORM = {
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


class SimulationInputError(ValueError):
    """Invalid simulator input; ``field`` maps to the form control."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class SpiceError(RuntimeError):
    """The solver ran but did not produce usable output."""

    def __init__(self, message: str, *, log: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.log = log


class SpiceUnavailable(SpiceError):
    """No ngspice executable could be located."""


@dataclass(frozen=True)
class CeInputs:
    vcc: float
    r1: float
    r2: float
    rc: float
    re: float
    rl: float
    cin_uf: float
    cout_uf: float
    bf: float
    amp_mv: float
    freq_hz: float
    fstart_hz: float
    fstop_hz: float
    ppd: int
    tstep_us: float
    tstop_ms: float

    @property
    def cin_f(self) -> float:
        return self.cin_uf * 1e-6

    @property
    def cout_f(self) -> float:
        return self.cout_uf * 1e-6

    @property
    def amp_v(self) -> float:
        return self.amp_mv * 1e-3

    @property
    def tstep_s(self) -> float:
        return self.tstep_us * 1e-6

    @property
    def tstop_s(self) -> float:
        return self.tstop_ms * 1e-3

    @property
    def model(self) -> str:
        return (
            f"{MODEL_NAME} NPN(IS={MODEL_IS:g} BF={self.bf:g} "
            f"VAF={MODEL_VAF:g})"
        )


@dataclass(frozen=True)
class OpResult:
    vb: float
    ve: float
    vc: float
    vce: float
    ic: float


@dataclass(frozen=True)
class AcResult:
    frequency: tuple[float, ...]
    gain_db: tuple[float, ...]
    phase_deg: tuple[float, ...]

    @property
    def gain_ratio(self) -> tuple[float, ...]:
        return tuple(10.0 ** (value / 20.0) for value in self.gain_db)


@dataclass(frozen=True)
class TranResult:
    time: tuple[float, ...]
    vin: tuple[float, ...]
    vout: tuple[float, ...]


@dataclass(frozen=True)
class SimulationResult:
    mode: str
    inputs: CeInputs
    version: str
    command: tuple[str, ...]
    log: str
    elapsed_s: float
    op: OpResult | None = None
    ac: AcResult | None = None
    tran: TranResult | None = None
    warnings: tuple[str, ...] = ()


def _required(raw: Mapping[str, str], field: str) -> float:
    text = (raw.get(field) or "").strip()
    if not text:
        raise SimulationInputError(field, f"กรุณากรอก {FIELD_LABELS[field]}")
    try:
        value = float(text)
    except ValueError:
        raise SimulationInputError(
            field, f"{FIELD_LABELS[field]} ต้องเป็นตัวเลข"
        ) from None
    return value


def _number(raw: Mapping[str, str], field: str, default: str) -> float:
    text = (raw.get(field) or "").strip()
    if not text:
        text = default
    try:
        return float(text)
    except ValueError:
        raise SimulationInputError(
            field, f"{FIELD_LABELS[field]} ต้องเป็นตัวเลข"
        ) from None


def parse_form(raw: Mapping[str, str], mode: str = "dc") -> CeInputs:
    """Parse and validate the simulator form for the selected analysis mode."""

    if mode not in ANALYSIS_MODES:
        raise SimulationInputError("analysis", f"โหมดวิเคราะห์ไม่ถูกต้อง: {mode}")

    vcc = _required(raw, "vcc")
    r1 = _required(raw, "r1")
    r2 = _required(raw, "r2")
    rc = _required(raw, "rc")
    re = _required(raw, "re")
    rl = _required(raw, "rl")
    cin_uf = _required(raw, "cin_uf")
    cout_uf = _required(raw, "cout_uf")
    bf = _required(raw, "bf")
    amp_mv = _number(raw, "amp_mv", DEFAULT_FORM["amp_mv"])
    freq_hz = _number(raw, "freq_hz", DEFAULT_FORM["freq_hz"])
    fstart_hz = _number(raw, "fstart_hz", DEFAULT_FORM["fstart_hz"])
    fstop_hz = _number(raw, "fstop_hz", DEFAULT_FORM["fstop_hz"])
    ppd_raw = _number(raw, "ppd", DEFAULT_FORM["ppd"])
    tstep_us = _number(raw, "tstep_us", DEFAULT_FORM["tstep_us"])
    tstop_ms = _number(raw, "tstop_ms", DEFAULT_FORM["tstop_ms"])

    if not math.isfinite(vcc) or not 0 < vcc <= 100:
        raise SimulationInputError("vcc", "VCC ต้องมากกว่า 0 และไม่เกิน 100 V")
    for field, value in (
        ("r1", r1),
        ("r2", r2),
        ("rc", rc),
        ("re", re),
        ("rl", rl),
    ):
        if not math.isfinite(value) or not 0 < value <= 1e9:
            raise SimulationInputError(
                field, f"{FIELD_LABELS[field]} ต้องมากกว่า 0 และไม่เกิน 1 GΩ"
            )
    for field, value in (("cin_uf", cin_uf), ("cout_uf", cout_uf)):
        if not math.isfinite(value) or not 0 < value <= 1e6:
            raise SimulationInputError(
                field, f"{FIELD_LABELS[field]} ต้องมากกว่า 0 µF"
            )
    if not math.isfinite(bf) or not 1 <= bf <= 10000:
        raise SimulationInputError("bf", "BF ต้องอยู่ระหว่าง 1 ถึง 10,000")

    if mode == "ac":
        if not math.isfinite(fstart_hz) or fstart_hz <= 0:
            raise SimulationInputError("fstart_hz", "f_start ต้องมากกว่า 0 Hz")
        if not math.isfinite(fstop_hz) or fstop_hz <= fstart_hz:
            raise SimulationInputError(
                "fstop_hz", "f_stop ต้องมากกว่า f_start"
            )
        if fstop_hz > 1e9:
            raise SimulationInputError("fstop_hz", "f_stop ต้องไม่เกิน 1 GHz")
        if not math.isfinite(ppd_raw) or ppd_raw != int(ppd_raw):
            raise SimulationInputError("ppd", "Points/decade ต้องเป็นจำนวนเต็ม")
        if not 1 <= int(ppd_raw) <= 100:
            raise SimulationInputError(
                "ppd", "Points/decade ต้องอยู่ระหว่าง 1 ถึง 100"
            )
    if mode == "tran":
        if not math.isfinite(amp_mv) or not 0 < amp_mv <= 5000:
            raise SimulationInputError(
                "amp_mv", "Amplitude ต้องมากกว่า 0 และไม่เกิน 5,000 mV"
            )
        if not math.isfinite(freq_hz) or not 0 < freq_hz <= 1e8:
            raise SimulationInputError(
                "freq_hz", "Frequency ต้องมากกว่า 0 และไม่เกิน 100 MHz"
            )
        if not math.isfinite(tstep_us) or tstep_us <= 0:
            raise SimulationInputError("tstep_us", "Time step ต้องมากกว่า 0 µs")
        if not math.isfinite(tstop_ms) or not 0 < tstop_ms <= 1000:
            raise SimulationInputError(
                "tstop_ms", "Stop time ต้องมากกว่า 0 และไม่เกิน 1,000 ms"
            )
        if tstep_us * 1e-6 > tstop_ms * 1e-3:
            raise SimulationInputError(
                "tstep_us", "Time step ต้องไม่มากกว่า Stop time"
            )
        if (tstop_ms * 1e-3) / (tstep_us * 1e-6) > 200000:
            raise SimulationInputError(
                "tstep_us", "จำนวนจุดเยอะเกินไป (สูงสุด 200,000 จุด)"
            )

    return CeInputs(
        vcc=vcc,
        r1=r1,
        r2=r2,
        rc=rc,
        re=re,
        rl=rl,
        cin_uf=cin_uf,
        cout_uf=cout_uf,
        bf=bf,
        amp_mv=amp_mv,
        freq_hz=freq_hz,
        fstart_hz=fstart_hz,
        fstop_hz=fstop_hz,
        ppd=int(ppd_raw),
        tstep_us=tstep_us,
        tstop_ms=tstop_ms,
    )


def _g(value: float) -> str:
    return f"{value:.12g}"


def build_netlist(mode: str, inputs: CeInputs) -> str:
    """Return a complete batch netlist for one analysis mode."""

    if mode not in ANALYSIS_MODES:
        raise ValueError(f"unknown analysis mode: {mode}")

    lines = [
        "* ENG29 2121 Lab 04 - CE voltage-divider amplifier (reference)",
        f"* analysis: {mode}",
        f"VCC vcc 0 {_g(inputs.vcc)}",
        f"VIN in 0 DC 0 AC 1 SIN(0 {_g(inputs.amp_v)} {_g(inputs.freq_hz)})",
        f"CIN in base {_g(inputs.cin_f)}",
        f"R1 vcc base {_g(inputs.r1)}",
        f"R2 base 0 {_g(inputs.r2)}",
        f"RC vcc coll {_g(inputs.rc)}",
        f"RE emit 0 {_g(inputs.re)}",
        f"Q1 coll base emit {MODEL_NAME}",
        f"COUT coll out {_g(inputs.cout_f)}",
        f"RL out 0 {_g(inputs.rl)}",
        f".model {inputs.model}",
    ]
    if mode == "dc":
        lines.append(".op")
        vectors = "v(base) v(emit) v(coll) @q1[ic]"
        outfile = "op.out"
    elif mode == "ac":
        lines.append(
            f".ac dec {inputs.ppd} {_g(inputs.fstart_hz)} {_g(inputs.fstop_hz)}"
        )
        vectors = "vdb(out) vp(out) vdb(in) vp(in)"
        outfile = "ac.out"
    else:
        lines.append(f".tran {_g(inputs.tstep_s)} {_g(inputs.tstop_s)}")
        vectors = "v(in) v(out)"
        outfile = "tran.out"
    lines.extend(
        [
            ".control",
            "run",
            "set wr_vecnames",
            "set wr_singlescale",
            f"wrdata {outfile} {vectors}",
            ".endc",
            ".end",
            "",
        ]
    )
    return "\n".join(lines)


def ngspice_binary() -> str:
    """Locate the batch-capable executable (console build preferred)."""

    override = os.environ.get("NGSPICE_BIN", "").strip()
    if override:
        if Path(override).is_file():
            return override
        raise SpiceUnavailable(
            f"NGSPICE_BIN ชี้ไปยังไฟล์ที่ไม่มีอยู่: {override}"
        )
    for name in ("ngspice_con", "ngspice"):
        found = shutil.which(name)
        if found:
            return found
    raise SpiceUnavailable(
        "ไม่พบ ngspice ใน PATH — ติดตั้ง ngspice แล้วตรวจคำสั่ง "
        "ngspice_con --version (Windows GUI build ไม่คืนผลทาง stdout)"
    )


_VERSION_RE = re.compile(r"ngspice-\d+(?:\.\d+)?")


def ngspice_version(binary: str | None = None) -> str:
    binary = binary or ngspice_binary()
    try:
        proc = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    match = _VERSION_RE.search(f"{proc.stdout}\n{proc.stderr}")
    return match.group(0) if match else "unknown"


def _read_wrdata(path: Path) -> tuple[list[str], list[list[float]]]:
    if not path.is_file():
        raise SpiceError(f"ไม่พบไฟล์ผลลัพธ์จาก ngspice: {path.name}")
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise SpiceError(f"ไฟล์ผลลัพธ์ว่างหรือไม่มีข้อมูล: {path.name}")
    headers = lines[0].split()
    rows: list[list[float]] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) != len(headers):
            continue
        try:
            values = [float(part) for part in parts]
        except ValueError:
            continue
        if all(math.isfinite(value) for value in values):
            rows.append(values)
    if not rows:
        raise SpiceError(f"อ่านค่าตัวเลขจาก {path.name} ไม่ได้")
    return headers, rows


def _column(headers: list[str], rows: list[list[float]], name: str) -> list[float]:
    try:
        index = headers.index(name)
    except ValueError:
        raise SpiceError(f"ไม่พบตัวแปร {name} ในผลลัพธ์ ngspice") from None
    return [row[index] for row in rows]


def _parse_op(path: Path) -> OpResult:
    headers, rows = _read_wrdata(path)
    vb = _column(headers, rows, "v(base)")[0]
    ve = _column(headers, rows, "v(emit)")[0]
    vc = _column(headers, rows, "v(coll)")[0]
    ic = _column(headers, rows, "@q1[ic]")[0]
    return OpResult(vb=vb, ve=ve, vc=vc, vce=vc - ve, ic=ic)


def _parse_ac(path: Path) -> AcResult:
    headers, rows = _read_wrdata(path)
    freq = _column(headers, rows, "frequency")
    out_db = _column(headers, rows, "vdb(out)")
    out_phase = _column(headers, rows, "vp(out)")
    in_db = _column(headers, rows, "vdb(in)")
    in_phase = _column(headers, rows, "vp(in)")
    gain_db = [out - ref for out, ref in zip(out_db, in_db)]
    phase = []
    for out_rad, in_rad in zip(out_phase, in_phase):
        degrees = math.degrees(out_rad - in_rad)
        degrees = (degrees + 180.0) % 360.0 - 180.0
        phase.append(degrees)
    return AcResult(
        frequency=tuple(freq), gain_db=tuple(gain_db), phase_deg=tuple(phase)
    )


def _parse_tran(path: Path) -> TranResult:
    headers, rows = _read_wrdata(path)
    time = _column(headers, rows, "time")
    vin = _column(headers, rows, "v(in)")
    vout = _column(headers, rows, "v(out)")
    return TranResult(time=tuple(time), vin=tuple(vin), vout=tuple(vout))


def _read_log(path: Path, fallback: str) -> str:
    if path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            return text
    return fallback


def simulate(
    mode: str,
    inputs: CeInputs,
    *,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> SimulationResult:
    """Run one analysis and return parsed results or raise ``SpiceError``."""

    if mode not in ANALYSIS_MODES:
        raise ValueError(f"unknown analysis mode: {mode}")
    binary = ngspice_binary()
    netlist = build_netlist(mode, inputs)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="lab04-ngspice-") as tmp:
        workdir = Path(tmp)
        circuit = workdir / "circuit.cir"
        circuit.write_text(netlist, encoding="ascii")
        command = (binary, "-b", "-o", "run.log", "circuit.cir")
        try:
            proc = subprocess.run(
                list(command),
                cwd=str(workdir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            raise SpiceUnavailable(
                f"เรียก ngspice ไม่ได้: {binary}"
            ) from None
        except subprocess.TimeoutExpired:
            raise SpiceError(
                f"ngspice ใช้เวลาเกิน {timeout:g} วินาที และถูกยกเลิก"
            ) from None
        elapsed = time.perf_counter() - started
        log = _read_log(workdir / "run.log", f"{proc.stdout}\n{proc.stderr}")
        if proc.returncode != 0:
            raise SpiceError(
                f"ngspice จบด้วยรหัส {proc.returncode} — ตรวจสอบค่าและ netlist",
                log=log,
            )
        if re.search(r"(?im)^\s*(error|fatal)\b", log):
            raise SpiceError("ngspice รายงานข้อผิดพลาด — ดู log", log=log)
        if mode == "dc":
            op = _parse_op(workdir / "op.out")
            return SimulationResult(
                mode=mode,
                inputs=inputs,
                version=ngspice_version(binary),
                command=command,
                log=log,
                elapsed_s=elapsed,
                op=op,
                warnings=(),
            )
        if mode == "ac":
            ac = _parse_ac(workdir / "ac.out")
            warnings = ()
            if ac.gain_db and max(ac.gain_db) == min(ac.gain_db):
                warnings = ("กราฟแบนในช่วง sweep — ยังสรุปจุดตัด −3 dB ไม่ได้",)
            return SimulationResult(
                mode=mode,
                inputs=inputs,
                version=ngspice_version(binary),
                command=command,
                log=log,
                elapsed_s=elapsed,
                ac=ac,
                warnings=warnings,
            )
        tran = _parse_tran(workdir / "tran.out")
        warnings = []
        cycles = inputs.tstop_s * inputs.freq_hz
        if cycles < 2:
            warnings.append(
                f"ช่วงจำลองครอบคลุมเพียง {cycles:.2f} รอบ (< 2 รอบ) — "
                "เพิ่ม Stop time หรือ Frequency"
            )
        return SimulationResult(
            mode=mode,
            inputs=inputs,
            version=ngspice_version(binary),
            command=command,
            log=log,
            elapsed_s=elapsed,
            tran=tran,
            warnings=tuple(warnings),
        )
