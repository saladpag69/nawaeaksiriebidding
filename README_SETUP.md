# ขั้นตอนติดตั้งและใช้งาน — ระบบประมูลภาครัฐ

## 1. ติดตั้ง Python packages

```bash
cd procurement_system
pip install -r requirements.txt
playwright install chromium
```

---

## 2. ตั้งค่า Google Sheets API (ครั้งเดียว)

### 2.1 สร้าง Google Cloud Project
1. ไปที่ https://console.cloud.google.com/
2. สร้าง Project ใหม่ → ตั้งชื่อว่า "ProcurementBot"
3. เปิด APIs & Services → **Enable APIs**
   - Google Sheets API ✅
   - Google Drive API ✅

### 2.2 สร้าง Service Account
1. IAM & Admin → **Service Accounts** → Create
2. ตั้งชื่อ: `procurement-bot`
3. Role: **Editor**
4. Keys → Add Key → JSON → Download
5. **เปลี่ยนชื่อไฟล์เป็น `credentials.json`**
6. วางไว้ในโฟลเดอร์ `procurement_system/`

### 2.3 แชร์ Google Sheet กับ Service Account
1. เปิด https://sheets.google.com
2. สร้าง Spreadsheet ใหม่ ชื่อ **"สรุปการค้นหางานประมูลภาครัฐ"**
3. กด Share → ใส่อีเมล์ Service Account (ดูใน credentials.json บรรทัด `client_email`)
4. ให้สิทธิ์ **Editor**

---

## 3. ตั้งค่า config.json

แก้ไขค่าใน `config.json`:

| ฟิลด์ | ความหมาย | ตัวอย่าง |
|-------|-----------|---------|
| `province_ids` | รหัสจังหวัดที่ต้องการ | `["14", "13"]` = อยุธยา, ปทุมธานี |
| `method_ids` | วิธีการจัดซื้อ | `["1"]` = e-Bidding, `["2"]` = e-Market |
| `price_min` | มูลค่าขั้นต่ำ (บาท) | `500000` |
| `price_max` | มูลค่าสูงสุด (บาท) | `50000000` |
| `days_ahead` | ดึงข้อมูลล่วงหน้ากี่วัน | `30` |

---

## 4. รันระบบ

```bash
# รันด้วย requests (เร็ว)
python main.py

# รันด้วย Playwright (ถ้า e-GP ต้อง JavaScript)
python main.py --playwright

# เขียนทับข้อมูลเก่า (แทนที่เพิ่มต่อท้าย)
python main.py --mode overwrite --playwright
```

---

## 5. ผลลัพธ์

- **Google Sheet**: สรุปการค้นหางานประมูลภาครัฐ
  - Sheet 1: `ผลการค้นหา` — รายการประมูลทั้งหมด
  - Sheet 2: `สรุปสถิติ` — จำนวนแยกตามจังหวัด/วิธีการ
- **CSV**: บันทึกในโฟลเดอร์ `results/`

---

## 6. วิธี filter ข้อมูล

แก้ `config.json` เพื่อเพิ่ม/ลดขอบเขต:

```json
"search_filters": {
  "province_ids": ["14", "13", "12"],     ← หลายจังหวัด
  "method_ids": ["1"],                     ← เฉพาะ e-Bidding
  "price_min": 1000000,                    ← ≥ 1 ล้านบาท
  "price_max": 50000000,                   ← ≤ 50 ล้านบาท
  "days_ahead": 60                         ← ดูล่วงหน้า 60 วัน
}
```

---

## 7. รหัสจังหวัดที่ใช้บ่อย

| รหัส | จังหวัด |
|------|---------|
| 14 | พระนครศรีอยุธยา |
| 13 | ปทุมธานี |
| 12 | นนทบุรี |
| 19 | สระบุรี |
| 18 | ชัยนาท |
| 15 | อ่างทอง |
| 10 | กรุงเทพมหานคร |
