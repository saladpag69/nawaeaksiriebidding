"""
อัปโหลดข้อมูลประมูลไปยัง Google Sheets
ใช้ gspread + google-auth (Service Account)
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

COLUMNS = [
    "วันที่ค้นหา",
    "จังหวัด",
    "วิธีการจัดหา",
    "ลำดับ",
    "หน่วยงาน",
    "ชื่อโครงการ",
    "วันที่ประกาศ",
    "วันที่ยื่นซอง",
    "วงเงินงบประมาณ",
    "สถานะ",
    "ลิงก์",
]


def get_client(credentials_file: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
    return gspread.authorize(creds)


def get_or_create_sheet(
    client: gspread.Client,
    spreadsheet_name: str,
    worksheet_name: str,
) -> tuple[gspread.Spreadsheet, gspread.Worksheet]:
    """เปิด spreadsheet ที่มีอยู่ หรือสร้างใหม่"""
    try:
        ss = client.open(spreadsheet_name)
        log.info(f"เปิด spreadsheet ที่มีอยู่: {spreadsheet_name}")
    except gspread.SpreadsheetNotFound:
        ss = client.create(spreadsheet_name)
        log.info(f"สร้าง spreadsheet ใหม่: {spreadsheet_name}")
        # แชร์ให้เจ้าของบัญชี (ใส่อีเมล์ผู้ใช้ถ้าต้องการ)
        # ss.share("your@email.com", perm_type="user", role="owner")

    # หาหรือสร้าง worksheet
    try:
        ws = ss.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=worksheet_name, rows=5000, cols=len(COLUMNS))
        log.info(f"สร้าง worksheet ใหม่: {worksheet_name}")

    return ss, ws


def ensure_header(ws: gspread.Worksheet) -> None:
    """ตรวจสอบ/เพิ่ม header row"""
    first_row = ws.row_values(1)
    if first_row != COLUMNS:
        ws.update("A1", [COLUMNS])
        # จัด format header
        ws.format("A1:J1", {
            "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.8},
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            "horizontalAlignment": "CENTER",
        })
        log.info("เพิ่ม header แล้ว")


def append_results(ws: gspread.Worksheet, data: list[dict]) -> int:
    """เพิ่มข้อมูลใหม่ต่อท้าย (ไม่ลบของเก่า)"""
    if not data:
        log.warning("ไม่มีข้อมูลให้อัปโหลด")
        return 0

    rows = [[row.get(col, "") for col in COLUMNS] for row in data]

    # หาแถวสุดท้ายที่มีข้อมูล
    existing = ws.get_all_values()
    next_row = len(existing) + 1

    ws.update(f"A{next_row}", rows)
    log.info(f"อัปโหลด {len(rows)} แถว (เริ่มที่แถว {next_row})")
    return len(rows)


def overwrite_results(ws: gspread.Worksheet, data: list[dict]) -> int:
    """ล้างข้อมูลเก่าแล้วเขียนใหม่ทั้งหมด"""
    ws.clear()
    ensure_header(ws)

    if not data:
        return 0

    rows = [[row.get(col, "") for col in COLUMNS] for row in data]
    ws.update("A2", rows)
    log.info(f"เขียนใหม่ {len(rows)} แถว")
    return len(rows)


def add_summary_sheet(ss: gspread.Spreadsheet, data: list[dict]) -> None:
    """เพิ่ม/อัปเดต sheet สรุป"""
    try:
        ws_sum = ss.worksheet("สรุปสถิติ")
    except gspread.WorksheetNotFound:
        ws_sum = ss.add_worksheet(title="สรุปสถิติ", rows=100, cols=5)

    ws_sum.clear()

    # สรุปตามจังหวัด
    province_count: dict[str, int] = {}
    method_count: dict[str, int] = {}
    for row in data:
        p = row.get("จังหวัด", "ไม่ระบุ")
        m = row.get("วิธีการจัดหา", "ไม่ระบุ")
        province_count[p] = province_count.get(p, 0) + 1
        method_count[m] = method_count.get(m, 0) + 1

    summary_rows = [
        ["สรุปการค้นหาประมูลภาครัฐ", ""],
        [f"วันที่รายงาน: {datetime.today().strftime('%d/%m/%Y %H:%M')}", ""],
        [f"รวมทั้งหมด: {len(data)} รายการ", ""],
        ["", ""],
        ["จำแนกตามจังหวัด", "จำนวน"],
    ] + [[p, c] for p, c in sorted(province_count.items(), key=lambda x: -x[1])] + [
        ["", ""],
        ["จำแนกตามวิธีการ", "จำนวน"],
    ] + [[m, c] for m, c in sorted(method_count.items(), key=lambda x: -x[1])]

    ws_sum.update("A1", summary_rows)
    log.info("อัปเดต sheet สรุปสถิติแล้ว")


def upload_to_sheets(data: list[dict], config: dict, mode: str = "append") -> str:
    """
    ฟังก์ชันหลัก: อัปโหลดไปยัง Google Sheets
    mode: 'append' = เพิ่มต่อท้าย | 'overwrite' = เขียนทับใหม่
    """
    gs_config = config["google_sheets"]
    credentials_file = gs_config.get("credentials_file", "credentials.json")
    ss_name = gs_config.get("spreadsheet_name", "สรุปการค้นหางานประมูลภาครัฐ")
    ws_name = gs_config.get("worksheet_name", "ผลการค้นหา")

    if not Path(credentials_file).exists():
        raise FileNotFoundError(
            f"ไม่พบไฟล์ credentials: {credentials_file}\n"
            "กรุณาดู README_SETUP.md เพื่อตั้งค่า Google Sheets API"
        )

    client = get_client(credentials_file)
    ss, ws = get_or_create_sheet(client, ss_name, ws_name)
    ensure_header(ws)

    if mode == "overwrite":
        count = overwrite_results(ws, data)
    else:
        count = append_results(ws, data)

    add_summary_sheet(ss, data)

    url = f"https://docs.google.com/spreadsheets/d/{ss.id}"
    log.info(f"✅ อัปโหลดสำเร็จ {count} รายการ → {url}")
    return url


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from procurement_scraper import load_config
    cfg = load_config()
    # ทดสอบ
    dummy = [{"วันที่ค้นหา": "01/06/2026", "จังหวัด": "อยุธยา", "วิธีการจัดหา": "e-Bidding",
              "เลขที่โครงการ": "TEST-001", "ชื่อโครงการ": "ทดสอบ", "หน่วยงาน": "ทดสอบ",
              "วงเงินงบประมาณ": "500000", "วันที่ยื่นซอง": "15/06/2026", "สถานะ": "ประกาศ", "ลิงก์": ""}]
    upload_to_sheets(dummy, cfg)
