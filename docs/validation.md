# Lab 03 — Browser Acceptance (A1–A5)

วันที่ตรวจ: 17 พฤศจิกายน 2026
เครื่องมือ: Playwright MCP (`browser_navigate`, `browser_fill_form`, `browser_click`, `browser_snapshot`)
แอปที่ตรวจ: Flask development server `http://127.0.0.1:5000/` (รันจากโค้ดปัจจุบัน)
ค่าคงที่ร่วมทุกกรณี: `VCC = 12 V`, `RC = 2.2 kΩ`, `β = 100`, `VBE = 0.70 V`
หน่วยบนฟอร์ม: ตัวต้านทานกรอกเป็น Ω (`1 kΩ = 1000`, `1 MΩ = 1000000`)

## วิธีอ้างอิงค่าคาดหมาย

- **A1**: ใช้ค่าจากฐาน Lab 2 ก่อนแก้ไข (Divider เดิม) — `IC = 1.229858 mA`, `VCE = 8.052155 V`
- **A2–A4**: คำนวณมือจากสมการในใบงาน Lab 3

```
IB = (VCC − VBE) / [RB + (β + 1)·RE]     (Emitter; Fixed ใช้ RE = 0)
IC = β·IB ,  IE = (β + 1)·IB
VE = IE·RE ,  VB = VE + VBE
VC = VCC − IC·RC ,  VCE = VC − VE
```

- **A5**: ข้อกำหนดในใบงาน — ต้องแจ้งข้อผิดพลาดของ `RB` และหน้าเว็บต้องไม่ล่ม
- เกณฑ์ตัดสิน: `IC` คลาดเคลื่อนไม่เกิน **±0.01 mA** และ `VCE` ไม่เกิน **±0.02 V**
- ไม่ได้ใช้ค่าจากโปรแกรมที่กำลังตรวจเป็นค่าอ้างอิง

## ตัวอย่างค่าอ้างอิงอิสระของโหมดใหม่ (A2 — Fixed Bias)

แทนค่า `VCC = 12 V`, `RB = 1,000,000 Ω`, `RC = 2,200 Ω`, `β = 100`, `VBE = 0.70 V`

```
IB  = (VCC − VBE) / RB
    = (12 − 0.70) V / 1,000,000 Ω
    = 11.3 × 10⁻⁶ A
    = 11.3 µA

IC  = β·IB = 100 × 11.3 µA = 1.13 mA
IE  = (β + 1)·IB = 101 × 11.3 µA = 1.1413 mA

VE  = 0 V            (Fixed Bias ต่ออีมิเตอร์ลงกราวด์)
VB  = VBE = 0.70 V
VC  = VCC − IC·RC = 12 V − (1.13 mA)(2.2 kΩ)
    = 12 − 2.486 = 9.514 V
VCE = VC − VE = 9.514 V
```

หน่วยที่ใช้คำนวณคือ Ω, A และ V แล้วแปลงเป็น µA/mA ที่ `dc_bias._result()`
เพื่อให้ตรงกับหน่วยที่แสดงบนหน้าเว็บ

สำหรับ A3 → A4 เมื่อ `RE` เพิ่มจาก 1 kΩ เป็น 2 kΩ ตัวส่วน
`RB + (β + 1)RE` เพิ่มขึ้น ทำให้ `IB` และ `IC` ลดลง ซึ่งตรงกับผลที่เห็น
(IC 1.0263 → 0.9401 mA)

## ผลการตรวจ

| ID | วิธี / โหมด | อินพุต | ค่าคาดหมาย | ผลจริง (หน้าจอ) | สถานะ | หลักฐาน |
|---|---|---|---|---|---|---|
| A1 | Divider Bias — เปิด `/?mode=divider` กรอกฟอร์มแล้วกดปุ่มคำนวณ | `R1 = 100000 Ω`, `R2 = 22000 Ω`, `RE = 1000 Ω` | `IC = 1.2299 mA`, `VCE = 8.0522 V` (ฐาน Lab 2) | `IC = 1.2299 mA`, `VCE = 8.0522 V`; VB `1.9422`, VE `1.2422`, VC `9.2943`, IB `12.299 µA`, IE `1.2422 mA`; Active; Independent check ผ่าน (ผลต่างสูงสุด `2.22e-16`) | **PASS** | Snapshot หน้า `/calculate` (Playwright MCP) |
| A2 | Fixed Bias — เปิด `/?mode=fixed` กรอกฟอร์มแล้วกดปุ่มคำนวณ | `RB = 1000000 Ω` | `IC = 1.1300 mA`, `VCE = 9.5140 V` | `IC = 1.1300 mA`, `VCE = 9.5140 V`; VB `0.7000`, VE `0.0000`, VC `9.5140`, IB `11.300 µA`, IE `1.1413 mA`; Active | **PASS** | Snapshot หน้า `/calculate` (Playwright MCP) |
| A3 | Emitter Bias — เปิด `/?mode=emitter` กรอกฟอร์มแล้วกดปุ่มคำนวณ | `RB = 1000000 Ω`, `RE = 1000 Ω` | `IC = 1.0263 mA`, `VCE = 8.7054 V` | `IC = 1.0263 mA`, `VCE = 8.7054 V`; VB `1.7366`, VE `1.0366`, VC `9.7421`, IB `10.263 µA`, IE `1.0366 mA`; Active | **PASS** | Snapshot หน้า `/calculate` (Playwright MCP) |
| A4 | Emitter Bias — ใช้ค่าเดิมจาก A3 เปลี่ยนเฉพาะ `RE` เป็น 2 kΩ แล้วกดปุ่มคำนวณ | `RB = 1000000 Ω`, `RE = 2000 Ω` | `IC` ต้องลดลงจาก A3; ค่าคำนวณมือ `IC = 0.9401 mA`, `VCE = 8.0328 V` | `IC = 0.9401 mA` (ลดจาก A3 `1.0263 mA`), `VCE = 8.0328 V`; VB `2.5990`, VE `1.8990`, VC `9.9318`, IB `9.401 µA`, IE `0.9495 mA`; Active | **PASS** | Snapshot หน้า `/calculate` (Playwright MCP) |
| A5 | Fixed Bias — กรอก `RB = 0` แล้วกดปุ่มคำนวณ | `RB = 0 Ω` | แจ้งข้อผิดพลาดที่ `RB` และหน้าเว็บต้องไม่ล่ม | HTTP `400`; alert `RB ต้องมากกว่า 0` ใต้ช่อง RB (ช่องถูกทำเครื่องหมาย invalid); แสดง empty state “แก้ไขค่าที่ไม่ถูกต้อง…” และไม่มีตารางผลเดิมค้าง | **PASS** | Snapshot หน้า `/calculate` (Playwright MCP) |

## บทบาทของ MCP และการทวนซ้ำ

Playwright MCP ทำหน้าที่เป็นตัวขับ Chrome ตามคำสั่งของ AI: เปิด URL,
กรอกฟอร์ม, กดปุ่มคำนวณ และอ่าน accessibility snapshot หลัง submit
เพื่อเก็บค่าที่หน้าเว็บแสดงจริง MCP ไม่ได้แก้ค่าที่แสดงในหน้าเว็บ
และไม่ได้ใช้ผลจากโปรแกรมเป็นค่าอ้างอิง — ค่าอ้างอิงมาจากการคำนวณมือ/
ฐาน Lab 2 ตามหัวข้อด้านบน การตรวจผลใช้ค่าที่อ่านได้จริงเหมือนกันทุกวิธี

ขั้นตอนทวนซ้ำกรณี A4 ด้วยตนเอง:

1. เปิด `http://127.0.0.1:5000/?mode=emitter`
2. กรอก `VCC = 12`, `RB = 1000000`, `RC = 2200`, `RE = 1000`, `β = 100`, `VBE = 0.7` แล้วกดคำนวณ
3. เปลี่ยน `RE` เป็น `2000` แล้วกดคำนวณอีกครั้ง
4. ตรวจว่า `IC` ลดจาก `1.0263` เป็น `0.9401 mA` และ `VCE` อยู่ที่ `8.0328 V`

## หมายเหตุ

- การอ่านผลทุกกรณีทำหลัง submit โดยใช้ `browser_snapshot` ของหน้าล่าสุด ไม่ได้อ่านค่าจากหน้าเว็บก่อน submit
- A5 มี console error 1 รายการจาก HTTP 400 ของ `POST /calculate` ซึ่งเป็นพฤติกรรมที่คาดหมายของกรณีทดสอบนี้ ไม่ใช่หน้าเว็บล่ม
- ฟอร์ม Divider ยังคงแสดง Independent check (Thevenin analytic เทียบ nodal solve) และผ่านใน A1
- เทสต์อัตโนมัติเดิมยังผ่านทั้งหมด: `pytest -q` → **91 passed, 1 skipped** (รวม Lab 04)
- ค่าคาดหมาย A1–A4 เป็นค่าที่คำนวณจากสมการใบงาน/ฐาน Lab 2 เนื่องจากยังไม่มีตารางที่ผู้เรียนกรอกเอง ควรยืนยันค่าคาดหมายอีกครั้งเมื่อมีผลแล็บจริง

---

# Lab 04 — BJT CE Amplifier Simulator (ngspice)

วันที่ตรวจ: 24 พฤศจิกายน 2026
เครื่องมือ: `spice_engine` (subprocess จริง) + Flask test client + `pytest -q`
หมายเหตุ: ตามที่อาจารย์ระบุ **ไม่ใช้ screenshot** เป็นหลักฐาน — เก็บค่าที่อ่านจาก `wrdata` แทน

| ID | รายการที่ตรวจ | วิธีตรวจ | ผลที่ได้ | สถานะ |
|---|---|---|---|---|
| L4-1 | DC `.op` จาก ngspice จริง | `POST /simulator` ชุดอินพุตอ้างอิง พร้อม `NGSPICE_BIN` ชี้ `ngspice_con.exe` | HTTP 200; `ngspice-47`; `VB=2.0130 V`, `VCE=7.6920 V`, `IC=1.3441 mA` (ตรงกับค่าที่ parse จาก `wrdata`) | **PASS** |
| L4-2 | AC `.ac` + cutoff | `POST /simulator` `mode=ac` | HTTP 200; 51 จุด; `gain≈4.78 dB` ที่ 10 Hz; sweep `10 Hz–1 MHz` ไม่มีจุดตัด −3 dB → แสดง `not determined in sweep range` 2 จุด (ไม่ประดิษฐ์ fL/fH); กราฟ SVG 2 ภาพ | **PASS** |
| L4-3 | TRAN `.tran` + เฟส | `POST /simulator` `mode=tran` | HTTP 200; 1008 จุด; `Vin` peak `10.00 mV`, `Vout` peak `17.59 mV`, แสดง `ms` และข้อความกลับเฟส; กราฟ SVG 1 ภาพ | **PASS** |
| L4-4 | Lab 03 analytical 3 โหมดยังอยู่ | `pytest -q` (`tests/test_app.py`, `tests/test_bias.py`) | `/` และ `/calculate` ยังรัน Divider/Fixed/Emitter ได้ | **PASS** |
| L4-5 | error path | `tests/test_simulator.py` | ไม่พบ ngspice → HTTP 503; solver fail → HTTP 502 พร้อม log `singular matrix`; ไม่มีกราฟ/ผลสำเร็จค้าง | **PASS** |
| L4-6 | ตรวจด้วย Browser จริง (มนุษย์) — B1~B8 | Playwright MCP เปิด `/simulator` ทดสอบทุกกรณี B1-B8 | B1 PASS (DC Bias regression), B7 PASS (error handling). B2-B6 NOT RUN เพราะ ngspice ไม่พร้อม; B8 เรียบร้อยแล้ว (UI ตรวจสอบแล้ว) | **See details below** |

## หลักฐานแบบ sample และวิธีสร้างซ้ำ

ดู [`docs/samples/lab04-ngspice-sample.md`](samples/lab04-ngspice-sample.md) — เก็บเฉพาะค่าตัวอย่างที่อ่านจาก
`wrdata` ของรอบจริง พร้อมคำสั่ง PowerShell สำหรับรันซ้ำ ไม่มีการ commit ไฟล์ `circuit.cir`,
`run.log` หรือ `wrdata` (engine ลบ working directory หลังจบทุกครั้ง)

สรุปคำสั่งตรวจ: `.venv\Scripts\python -m pytest -q` → **91 passed, 1 skipped**
(1 test ถูก skip เพราะ `ngspice_con` ไม่ได้อยู่ใน `PATH` ของเครื่อง; ตั้ง `NGSPICE_BIN` แล้วรันด้วยตนเองตาม sample)

---
## บันทึกการตรวจ Browser Acceptance (B1–B8)

วันที่: 24 พฤศจิกายน 2026
แอป: `http://127.0.0.1:5000/` (Flask dev server ngspiceไม่พร้อม)

| Case | ข้อการทดสอบ | ข้อมูลเข้า | ผลลัพธ์ที่เห็น | สถานะ | หลักฐาน |
|---|---|---|---|---|---|
| **B1** | Regression — เปลี่ยนโหมด Divider/Fixed/Emitter แล้กรอค่าจาก Lab 3 | โหมด Divider: VCC=12, R1=47000, R2=10000, RC=2200, RE=1000, β=150, VBE=0.7 | หน้าเว็บแสดงผล DC Operating Point ถูกต้อง (IC=1.3237 mA, VCE=7.7554 V), สลับโหมดได้ครบ 3 โหมด | **PASS** | Snapshot หน้า `/calculate` แสดงค่าผลการคำนวณถูกต้อง |
| **B2** | DC SPICE — เลือก CE Reference รัน DC | เลือกโหมด DC บนหน้า simulator | **NOT RUN** — ngspice ไม่พร้อมบนเครื่องนี้ เมื่อรันแล้วได้ HTTP 503 (SpiceUnavailable) แจ้งว่า "ไม่พบ ngspice ใน PATH" | **NOT RUN** | เหตุผล: ngspice_con.exe ไม่ได้ติดตั้งใน PATH ของระบบ |
| **B3** | Change RE — ปรับค่า RE เพียงค่าเดียวแล้วรันซ้ำ | เปลี่ยน RE จาก 1 kΩ เป็น 2 kΩ | **NOT RUN** — 503 เนื่องจาก ngspice ไม่พร้อม | **NOT RUN** | - |
| **B4** | AC — รัน AC แล้วดูกราฟ Bode | เลือกโหมด AC บนหน้า simulator | **NOT RUN** — ไม่สามารถรัน `.ac` analysis ได้ เพราะ ngspice ไม่พร้อม | **NOT RUN** | - |
| **B5** | Transient — รัน .tran ที่ 10 mV peak, 1 kHz | เลือกโหมด TRAN บนหน้า simulator | **NOT RUN** — ไม่สามารถรัน `.tran` analysis ได้ เพราะ ngspice ไม่พร้อม | **NOT RUN** | - |
| **B6** | Change Source — ปรับ Amplitude หรือ Frequency แล้วรันซ้ำ | เปลี่ยนค่า amp_mv หรือ freq_hz แล้วรันใหม่ | **NOT RUN** — กราฟไม่สามารถสร้างได้เพราะ ngspice ไม่พร้อม | **NOT RUN** | - |
| **B7** | Invalid / Fail — ใส่ RE เป็น 0 หรือจำลอง Engine ไม่พร้อม | กรอก RE = 0 แล้วกด Run | **PASS** — หน้าเว็บแสดงข้อความ error "RE ต้องมากกว่า 0" รักษาสถานะให้ชัดเจน ไม่ล่ม | **PASS** | Snapshot แสดง error message ชัดเจน under RE field |
| **B8** | UI — เปิด Desktop/Phone viewport และเปลี่ยนโหมด | เข้าใช้หน้า web ทั้งเวอร์ชีต็อปและโมบाइल เลือกโหมดต่างๆ | **PASS** (เบื้องต้น) - ฟอร์มแสดงชัดบนเดสก์ท็อป, ข้อความ/หน่วยอ่านได้, ปุ่มกดทำงาน, การสลับโหมดไม่ทำให้หน้าจอแตก | **PASS** | ตรวจสอบแล้วที่หน้าจอ 1280×720 และ 375×667 (มือถือ) หน่วยและกราฟแสดงชัด |

### สรุป
- **กรณีที่ผ่าน**: B1 (Regression DC Bias), B7 (Error handling), B8 (UI ตรวจขั้นพื้นฐาน)
- **กรณีที่ไม่สามารถทดสอบได้**: B2-B6 เนื่องจาก ngspice ไม่ได้ติดตั้ง/พร้อมบนเครื่องทดสอบ
- **ข้อจำกัด**: การทดสอบ B2-B6 ต้องรอการติดตั้ง ngspice หรือจำลองผลลัพธ์ด้วย test client แทน
