# Lab 04 — ngspice sample (ngspice-47)

ตัวอย่างนี้เก็บเฉพาะค่าที่ **`spice_engine.simulate()` อ่านจากไฟล์ `wrdata` ของรอบจริง**
ไม่ใช่ค่าที่ hard-code ไว้ในโค้ด และไม่มีไฟล์รัน (`circuit.cir`, `run.log`, `wrdata`) ถูก commit
เพราะ engine สร้างใน `tempfile.TemporaryDirectory()` แล้วลบทิ้งหลังจบแต่ละรอบ

## วิธีสร้างซ้ำ (PowerShell)

```powershell
$env:NGSPICE_BIN = "C:\Users\b6826727\AppData\Local\Programs\ngspice\Spice64\bin\ngspice_con.exe"
.\.venv\Scripts\python -m pytest -q
```

หรือเรียก engine โดยตรง (อินพุตชุดเดียวกับฟอร์มLab 04):

```powershell
$env:NGSPICE_BIN = "..."
.\.venv\Scripts\python -c "import spice_engine as s; r=s.simulate('dc', s.parse_form(s.DEFAULT_FORM,'dc')); print(r.op)"
```

`NGSPICE_BIN` สามารถเปลี่ยนเป็น path ของ `ngspice_con.exe` ในเครื่องอื่นได้
(หรือใส่ `ngspice_con` ไว้ใน `PATH` แล้วไม่ต้อง set ตัวแปร)

## อินพุตอ้างอิง (`spice_engine.DEFAULT_FORM`)

`VCC=12 V`, `R1=100 kΩ`, `R2=22 kΩ`, `RC=2.2 kΩ`, `RE=1 kΩ`, `RL=10 kΩ`,
`Cin=Cout=10 µF`, `BF=150`, `Vin=10 mV peak`, `f=1 kHz`,
AC sweep `10 Hz–1 MHz` @ `10 points/decade`, TRAN `5 µs / 5 ms`

## ผลที่อ่านได้จริง (ตัวอย่าง)

| Analysis | ค่าที่อ่านจาก `wrdata` |
|---|---|
| `.op` | `V(B)=2.01301551 V`, `V(E)=1.35200569 V`, `V(C)=9.04399957 V`, `VCE=7.69199388 V`, `IC=1.34412619 mA` |
| `.ac` | 51 จุด; ที่ ~3.16 kHz `gain=4.8951 dB`, `phase=-179.96°`; ที่ 10 Hz `gain=4.7801 dB` |
| `.ac` cutoffs | ไม่มีจุดตัด −3 dB ในช่วง sweep → UI แสดง `not determined in sweep range` (ไม่สร้างตัวเลขขึ้นเอง) |
| `.tran` | 1008 จุด; `Vin` peak `9.9996 mV`, `Vout` peak `17.5904 mV`, `t_end=5.0 ms` |

ค่าที่ UI แสดงหลัง POST จริง: DC `2.0130 V / 7.6920 V / 1.3441 mA`,
AC `4.78 dB` พร้อมกราฟ 2 ภาพ, TRAN `10.00 mV / 17.59 mV` พร้อมกราฟ 1 ภาพ

> หมายเหตุ: เลขด้านบนเป็น snapshot จากรอบที่ตรวจในเครื่องนี้ (Windows, ngspice-47)
> ผลจากเครื่องอื่นอาจต่างเล็กน้อยตามเวอร์ชัน ngspice/model card; ให้รันคำสั่งข้างบนเพื่อสร้างใหม่เสมอ
