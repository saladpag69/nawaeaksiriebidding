"""
ระบบตรวจสอบงานประมูลภาครัฐอัตโนมัติ
รันได้ทั้งแบบ manual และ scheduled (ทุกวัน 7:00)
"""

import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def save_local_csv(data: list[dict], path: str) -> None:
    if not data:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(data[0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    log.info(f"บันทึก CSV: {path}")


def run(mode: str = "append", use_playwright: bool = False):
    """
    mode: 'append' = เพิ่มต่อท้าย | 'overwrite' = เขียนทับ
    use_playwright: True = ใช้ Playwright (สำหรับ JS-rendered pages)
    """
    log.info("=" * 60)
    log.info(f"เริ่มต้นระบบตรวจสอบประมูลภาครัฐ — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    log.info("=" * 60)

    # โหลด config
    script_dir = Path(__file__).parent
    cfg = json.load(open(script_dir / "config.json", encoding="utf-8"))

    # ดึงข้อมูล (รันรอบเดียว — ไม่ซ้ำ)
    from procurement_scraper import scrape_egp, scrape_egp_playwright

    if use_playwright:
        # ใช้ Playwright โดยตรง ไม่ผ่าน requests
        data = scrape_egp_playwright(cfg)
    else:
        # ใช้ requests เท่านั้น ไม่ fallback
        data = scrape_egp(cfg)

    if not data:
        log.warning("⚠️ ไม่พบข้อมูลการประมูล")
        return

    log.info(f"พบข้อมูล {len(data)} รายการ")

    # บันทึก CSV local
    if cfg.get("output", {}).get("save_local_csv"):
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        csv_path = str(script_dir / f"results/procurement_{ts}.csv")
        save_local_csv(data, csv_path)

    # อัปโหลด Google Sheets
    try:
        from sheets_uploader import upload_to_sheets
        url = upload_to_sheets(data, cfg, mode=mode)
        log.info(f"🔗 Google Sheet: {url}")
        print(f"\n✅ สำเร็จ! ดูผลได้ที่:\n{url}")
    except FileNotFoundError as e:
        log.error(str(e))
        print(f"\n⚠️ ยังไม่ได้ตั้งค่า Google Sheets API\nข้อมูลถูกบันทึกไว้ใน CSV แทน")
    except Exception as e:
        log.error(f"อัปโหลด Sheets ล้มเหลว: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ระบบค้นหาประมูลภาครัฐ e-GP")
    parser.add_argument("--mode", choices=["append", "overwrite"], default="append",
                        help="append=เพิ่มต่อท้าย, overwrite=เขียนทับ")
    parser.add_argument("--playwright", action="store_true",
                        help="ใช้ Playwright สำหรับ JS-rendered pages")
    args = parser.parse_args()
    run(mode=args.mode, use_playwright=args.playwright)
