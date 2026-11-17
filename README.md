ชื่อโครงงาน: DC Circuit Calculator

คำอธิบาย:

โปรแกรมช่วยคำนวณและวิเคราะห์พารามิเตอร์ทางไฟฟ้าในวงจรไฟฟ้ากระแสตรง (DC)
ที่ประกอบด้วยตัวต้านทาน ช่วยให้ผู้ใช้สามารถหาค่ากระแสไฟฟ้ารวม กระแสไฟฟ้าย่อย
และกำลังไฟฟ้าของแต่ละส่วนในวงจรได้อย่างรวดเร็ว

## BJT DC Bias Web App (Lab 03)

แอป Flask สำหรับคำนวณจุดทำงาน DC ของวงจรไบอัส BJT แบบ common-emitter
รองรับสามโหมดจากแหล่งจ่ายเดียว

| โหมด | อินพุตตัวต้านทาน | สมการกระแสฐาน |
|---|---|---|
| Voltage Divider Bias | R1, R2, RE | `IB = (VTH - VBE) / [RTH + (β + 1)RE]` |
| Fixed Bias | RB | `IB = (VCC - VBE) / RB` |
| Emitter Bias | RB, RE | `IB = (VCC - VBE) / [RB + (β + 1)RE]` |

ทุกโหมดใช้ `IC = β·IB`, `IE = (β + 1)·IB`, `VC = VCC - IC·RC` และ
`VCE = VC - VE`; Fixed Bias ใช้ `VE = 0` และ Emitter/Divider ใช้
`VE = IE·RE`

ผลลัพธ์จากโมดูล Python ใช้ dict ชื่อคีย์และหน่วยร่วมกัน:
`vb_v`, `ve_v`, `vc_v`, `vce_v`, `ib_ua`, `ic_ma`, `ie_ma`
พร้อม `region` และ `warnings` ส่วนการจัดรูปแบบทศนิยมทำในชั้น Flask

ตัวต้านทานในฟอร์มกรอกเป็น Ω เช่น 1 kΩ = `1000` และ 1 MΩ = `1000000`
ค่าที่คำนวณได้จะเตือนเมื่อ `IB ≤ 0` หรือ `VCE ≤ 0.2 V` ว่าแบบจำลอง
Forward Active อาจใช้ไม่ได้

### ลิงก์งานและ Commit

- GitHub: https://github.com/Phitchapha-dotcom/eng29-2121-git-lab01
- Commit SHA ของโค้ด Lab 03 และผลตรวจ A1–A5:
  `e7071d897da0403b81dec5bb3db9ac0a85659720`
- ผลตรวจ Browser: [`docs/validation.md`](docs/validation.md)

### AI ช่วยส่วนไหน และนักศึกษาตรวจอะไร

- AI ช่วยร่างสมการ Fixed/Emitter ใน `dc_bias.py`, ปรับ `app.py`/เทมเพลต/สไตล์
  และบันทึกผลตรวจ Browser ลง `docs/validation.md`
- นักศึกษาตรวจสูตรกับใบงาน ค่าอ้างอิงที่คำนวณมือ หน่วย และการคงผลเดิมของ
  Divider รวมทั้งทวนผลใน Browser อย่างน้อยหนึ่งกรณี
- โค้ดเลือกฟังก์ชันตามโหมดที่ `app._calculate()` ด้วย `if/elif/else`
  (`"divider"`, `"fixed"`, `"emitter"`); โหมดที่ไม่รู้จักจะไม่ fallback
- โค้ดแปลงหน่วย A → µA/mA ที่ `dc_bias._result()` ส่วนฟอร์มรับตัวต้านทานเป็น Ω
  และ `app.py` ทำหน้าที่จัดรูปแบบทศนิยมเพื่อแสดงผลเท่านั้น

### วิธีรัน

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m flask --app app run
```

เปิด http://127.0.0.1:5000/ แล้วเลือกโหมดจากแท็บด้านบน

### วิธีทดสอบ

```powershell
.venv\Scripts\python -m pytest -q
```

### การตรวจผ่าน Browser

ใช้ตาราง A1–A5 ของผู้เรียนเป็นค่าคาดหมาย แล้วตรวจหน้าเว็บจริงทีละกรณี
โดยเลือกโหมด กรอกค่าตามหน่วยบนฟอร์ม กดคำนวณ และอ่านผลใหม่หลัง submit
ทุกครั้ง บันทึกผลลง [`docs/validation.md`](docs/validation.md) พร้อมวิธีตรวจและหลักฐาน

ผลตรวจ A1–A5 ล่าสุด: ผ่านทั้งหมด 5 กรณี (ดูตารางและข้อความผลจาก snapshot ใน `docs/validation.md`)
