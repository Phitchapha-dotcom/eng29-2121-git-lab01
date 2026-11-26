# Submission Checklist — Lab 04 — BJT CE Amplifier Simulator (ngspice)

**หลักฐาน**: เก็บค่าจาก `wrdata` ของรันจริง via `spice_engine.simulate()`  
**คำสั่งตรวจ**: `.venv\Scripts\python -m pytest -q` → **91 passed, 1 skipped**  
**หมายเหตุ**: ไม่ใช้ screenshot เป็นหลักฐาน — ใช้ค่าที่อ่านจาก `wrdata` แทน ไม่มีการ commit ไฟล์ `circuit.cir`, `run.log` หรือ `wrdata` (engine ลบ working directory หลังจบทุกครั้ง)

| ID | รายการที่ตรวจ | วิธีตรวจ | ผลที่ได้ | สถานะ | หลักฐาน |
|---|---|---|---|---|---|
| L4-1 | DC `.op` จาก ngspice จริง | `POST /simulator` ชุดอินพุตอ้างอิง พร้อม `NGSPICE_BIN` ชี้ `ngspice_con.exe` | HTTP 200; `ngspice-47`; `VB=2.0130 V`, `VCE=7.6920 V`, `IC=1.3441 mA` (ตรงกับค่าที่ parse จาก `wrdata`) | **PASS** | Snapshot หน้า `/simulator` หลังรัน DC (Playwright MCP) |
| L4-2 | AC `.ac` + cutoff | `POST /simulator` `mode=ac` | HTTP 200; 51 จุด; `gain≈4.78 dB` ที่ 10 Hz; sweep `10 Hz–1 MHz` ไม่มีจุดตัด −3 dB → แสดง `not determined in sweep range` 2 จุด (ไม่ประดิษฐ์ fL/fH); กราฟ SVG 2 ภาพ | **PASS** | Snapshot หน้า `/simulator` หลังรัน AC (Playwright MCP) |
| L4-3 | TRAN `.tran` + เฟส | `POST /simulator` `mode=tran` | HTTP 200; 1008 จุด; `Vin` peak `10.00 mV`, `Vout` peak `17.59 mV`, แสดง `ms` และข้อความกลับเฟส; กราฟ SVG 1 ภาพ | **PASS** | Snapshot หน้า `/simulator` หลังรัน TRAN (Playwright MCP) |
| L4-4 | Lab 03 analytical 3 โหมดยังอยู่ | `pytest -q` (`tests/test_app.py`, `tests/test_bias.py`) | `/` และ `/calculate` ยังรัน Divider/Fixed/Emitter ได้ | **PASS** | ผลการรัน `pytest -q` แสดงคะแนนผ่าน |
| L4-5 | error path | `tests/test_simulator.py` | ไม่พบ ngspice → HTTP 503; solver fail → HTTP 502 พร้อม log `singular matrix`; ไม่มีกราฟ/ผลสำเร็จค้าง | **PASS** | ผลการทดสอบ error handling |
| L4-6 | ตรวจด้วย Browser จริง (มนุษย์) | เปิด `/simulator` แล้วกด Run ทั้ง 3 โหมด | ยังไม่ได้ทำในรอบนี้ (ใช้ test client + ngspice จริงแทน) | **NOT RUN** | — |

## ขั้นตอนการสร้างหลักฐานซ้ำ (PowerShell)

```powershell
# ตั้งค่าพาธ ngspice (ปรับให้ตรงกับเครื่องของตนเอง)
$env:NGSPICE_BIN = "C:\Users\b6826727\AppData\Local\Programs\ngspice\Spice64\bin\ngspice_con.exe"

# รันการทดสอบ
.venv\Scripts\python -m pytest -q
```

## อินพุตอ้างอิง (`spice_engine.DEFAULT_FORM`)

`VCC=12 V`, `R1=100 kΩ`, `R2=22 kΩ`, `RC=2.2 kΩ`, `RE=1 kΩ`, `RL=10 kΩ`,  
`Cin=Cout=10 µF`, `BF=150`, `Vin=10 mV peak`, `f=1 kHz`,  
AC sweep `10 Hz–1 MHz` @ `10 points/decade`, TRAN `5 µs / 5 ms`

## ผลที่อ่านได้จริง (ตัวอย่างรอบล่าสุด)

| Analysis | ค่าที่อ่านจาก `wrdata` |
|---|---|
| `.op` | `V(B)=2.01301551 V`, `V(E)=1.35200569 V`, `V(C)=9.04399957 V`, `VCE=7.69199388 V`, `IC=1.34412619 mA` |
| `.ac` | 51 จุด; ที่ ~3.16 kHz `gain=4.8951 dB`, `phase=-179.96°`; ที่ 10 Hz `gain=4.7801 dB` |
| `.ac` cutoffs | ไม่มีจุดตัด −3 dB ในช่วง sweep → UI แสดง `not determined in sweep range` (ไม่สร้างตัวเลขขึ้นเอง) |
| `.tran` | 1008 จุด; `Vin` peak `9.9996 mV`, `Vout` peak `17.5904 mV`, `t_end=5.0 ms` |

ค่าที่ UI แสดงหลัง POST จริง:  
- DC `2.0130 V / 7.6920 V / 1.3441 mA`  
- AC `4.78 dB` พร้อมกราฟ 2 ภาพ  
- TRAN `10.00 mV / 17.59 mV` พร้อมกราฟ 1 ภาพ

> **หมายเหตุ**: เลขด้านบนเป็น snapshot จากรอบที่ตรวจในเครื่องนี้ (Windows, ngspice-47)  
> ผลจากเครื่องอื่นอาจต่างเล็กน้อยตามเวอร์ชัน ngspice/model card; ให้รันคำสั่งข้างบนเพื่อสร้างใหม่เสมอ

## บทสรุป

- ทุกข้อบังคับ L4-1 ถึง L4-5 ผ่านเรียบร้อยแล้ว
- L4-6 (การตรวจเบราว์เซอร์จริง) ยังไม่ได้รันในรอบนี้ — ควรจะมีการรันด้วยตนเองหรืออัตโนมัติก่อนส่งมอบ
- 1 test ถูก skip เพราะ `ngspice_con` ไม่ได้อยู่ใน `PATH` ของเครื่อง; ตั้ง `NGSPICE_BIN` แล้วรันด้วยตนเองตาม sample