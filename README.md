ชื่อโครงงาน: DC Circuit Calculator

คำอธิบาย:

โปรแกรมช่วยคำนวณและวิเคราะห์พารามิเตอร์ทางไฟฟ้าในวงจรไฟฟ้ากระแสตรง (DC) ที่ประกอบด้วยตัวต้านทาน ช่วยให้ผู้ใช้สามารถหาค่ากระแสไฟฟ้ารวม กระแสไฟฟ้าย่อย และกำลังไฟฟ้าของแต่ละส่วนในวงจรได้อย่างรวดเร็ว เหมาะสำหรับการใช้งานเป็นเครื่องมือช่วยเรียนรู้และตรวจสอบความถูกต้องในการแก้โจทย์วิเคราะห์วงจร

## BJT Common-Emitter DC Bias Web App

แอป Flask สำหรับคำนวณจุดทำงาน DC ของวงจรไบอัส BJT แบบ common-emitter
(วงจรแบ่งแรงดัน) พร้อมตรวจสอบข้อมูลนำเข้า เตือนช่วง cutoff/saturation และ
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