# -*- coding: utf-8 -*-
"""
e-GP Procurement Scraper
URL: https://process3.gprocurement.go.th/egp2procmainWeb/procsearch.sch
"""

import requests
import json
import re
import time
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_URL    = "https://process3.gprocurement.go.th"
SEARCH_PATH = "/egp2procmainWeb/procsearch.sch"
ANNOUNCE_TYPE = "2"   # 2 = e-bidding invitation

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8",
    "Referer": "https://process3.gprocurement.go.th/egp2procmainWeb/jsp/public_announ_search.jsp",
}

METHOD_MAP = {
    "1": "e-Bidding",
    "2": "e-Market",
    "3": "Selective",
    "4": "Specific",
}

COLUMNS = [
    "date_searched", "province", "method",
    "project_no", "project_name", "department",
    "budget", "submission_date", "status", "link"
]

COLUMNS_TH = [
    "วันที่ค้นหา", "จังหวัด", "วิธีการจัดหา",
    "เลขที่โครงการ", "ชื่อโครงการ", "หน่วยงาน",
    "วงเงินงบประมาณ", "วันที่ยื่นซอง", "สถานะ", "ลิงก์"
]


def load_config(config_path="config.json"):
    path = Path(config_path)
    if not path.exists():
        path = Path(__file__).parent / config_path
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_date_range(config):
    """
    หลักการคำนวณวันที่ (ลำดับความสำคัญ):
    1. ถ้าใส่ date_start + date_end ใน config → ใช้ค่านั้นตรง ๆ
    2. ถ้าใส่ days_behind และ/หรือ days_ahead → คำนวณจากวันนี้
       เช่น days_behind=7, days_ahead=0 → ย้อนหลัง 7 วัน ถึงวันนี้
    3. default: ย้อนหลัง 30 วัน ถึงวันนี้
    """
    filters = config["search_filters"]
    today = datetime.today()

    # Priority 1: กำหนดวันที่เองตรง ๆ
    if filters.get("date_start") and filters.get("date_end"):
        return filters["date_start"], filters["date_end"]

    # Priority 2: คำนวณจาก days_behind / days_ahead
    days_behind = filters.get("days_behind", 30)   # ย้อนหลังกี่วัน
    days_ahead  = filters.get("days_ahead", 0)     # ล่วงหน้ากี่วัน

    date_start = today - timedelta(days=days_behind)
    date_end   = today + timedelta(days=days_ahead)

    log.info("Date range: %s -> %s (-%dd / +%dd)",
             date_start.strftime("%d/%m/%Y"), date_end.strftime("%d/%m/%Y"),
             days_behind, days_ahead)

    return date_start.strftime("%d/%m/%Y"), date_end.strftime("%d/%m/%Y")


def build_url(prov_id, met_id, price_min, price_max, date_start, date_end, page=1, per_page=20):
    # parameter names confirmed via browser inspection 2026:
    # moiId = province (140000=Ayutthaya, 190000=Saraburi)
    # methodId = method (16=e-bidding, 15=e-market)
    ds = date_start.replace("/", "%2F")
    de = date_end.replace("/", "%2F")
    return (
        BASE_URL + SEARCH_PATH
        + "?homeflag=A"
        + "&proc_id=FPRO9965"
        + "&servlet=FPRO9965Servlet"
        + "&announceType=" + ANNOUNCE_TYPE
        + "&moiId=" + str(prov_id)
        + "&methodId=" + str(met_id)
        + "&budgetMin=" + str(price_min)
        + "&budgetMax=" + str(price_max)
        + "&fromDate=" + ds
        + "&toDate=" + de
        + "&pageSize=" + str(per_page)
        + "&pageNo=" + str(page)
    )


def parse_results(soup, prov_name, met_name):
    """
    แก้ Bug 1: กรองเฉพาะแถวที่ cell[0] เป็นตัวเลขลำดับ (1, 2, 3...)
    เพื่อข้าม: แถว form HTML, แถว header, แถว pagination
    """
    rows = []
    table = (
        soup.find("table", id=re.compile(r"data|result|list|grid", re.I))
        or soup.find("table", class_=re.compile(r"table|result|list|grid", re.I))
        or soup.find("table")
    )
    if not table:
        return rows

    all_rows = table.find_all("tr")
    if len(all_rows) <= 1:
        return rows

    now_str = datetime.today().strftime("%d/%m/%Y %H:%M")
    for tr in all_rows:
        cells = tr.find_all("td")           # ใช้ td เท่านั้น (ไม่รวม th = header)
        if len(cells) < 4:
            continue
        texts = [c.get_text(separator=" ", strip=True) for c in cells]

        # Bug 1 Fix: ข้ามแถวที่ cell[0] ไม่ใช่ตัวเลข (เลขลำดับ 1, 2, 3...)
        seq = texts[0].strip()
        if not seq.isdigit():
            continue

        # e-GP column order: [ลำดับ, หน่วยงาน, เรื่อง, วันที่ประกาศ, งบประมาณ, สถานะ, ...]
        row = {
            "วันที่ค้นหา":    now_str,
            "จังหวัด":         prov_name,
            "วิธีการจัดหา":   met_name,
            "ลำดับ":           seq,
            "หน่วยงาน":        texts[1] if len(texts) > 1 else "",
            "ชื่อโครงการ":     texts[2] if len(texts) > 2 else "",
            "วันที่ประกาศ":    texts[3] if len(texts) > 3 else "",
            "วงเงินงบประมาณ": texts[4] if len(texts) > 4 else "",
            "สถานะ":           texts[5] if len(texts) > 5 else "",
            "ลิงก์":           "",
        }

        # ดึง project number จาก link เพื่อใช้ dedup
        a_tag = cells[2].find("a", href=True) if len(cells) > 2 else None
        if a_tag:
            href = a_tag["href"]
            row["ลิงก์"] = href if href.startswith("http") else BASE_URL + href
            proj_match = re.search(r"[?&]projectId=([^&]+)|proj_id=([^&]+)|(\d{11,})", href)
            if proj_match:
                row["_proj_key"] = proj_match.group(1) or proj_match.group(2) or proj_match.group(3)
        # fallback: ใช้ชื่อโครงการ+หน่วยงาน เป็น key
        if "_proj_key" not in row:
            row["_proj_key"] = row["หน่วยงาน"] + "|" + row["ชื่อโครงการ"][:50]

        rows.append(row)
    return rows


def get_total_pages(soup, per_page=10):
    """
    แก้ Bug 2: e-GP แสดงผล 10 รายการ/หน้า (ไม่ใช่ 20)
    และถ้า Playwright ได้ข้อมูลทั้งหมดในหน้าแรก (items > per_page แต่ table มีข้อมูลครบ)
    ให้ return 1 เพื่อไม่ loop ซ้ำ
    """
    text = soup.get_text()

    # ตรวจว่า "ลำดับที่ X - Y จากทั้งหมด Z" → ใช้ Y กับ per_page จาก pagination จริง
    m_range = re.search(r"ลำดับที่\s*(\d+)\s*-\s*(\d+)\s*จากทั้งหมด", text)
    if m_range:
        shown_from = int(m_range.group(1))
        shown_to   = int(m_range.group(2))
        items_this_page = shown_to - shown_from + 1

        # ถ้า Playwright ได้ข้อมูลหน้านี้ครบ (items_this_page >= total ที่จะมี)
        # นับจากตาราง: ถ้ามี row data มากกว่า per_page → น่าจะได้ทั้งหมดแล้ว
        actual_rows = len([
            tr for tr in soup.find_all("tr")
            if tr.find_all("td") and len(tr.find_all("td")) >= 4
            and tr.find_all("td")[0].get_text(strip=True).isdigit()
        ])
        if actual_rows >= items_this_page:
            # ข้อมูลในหน้านี้ครบตาม pagination range → หา total แล้วคำนวณ
            m_total = re.search(r"มากกว่า\s*(\d+)|จากทั้งหมด\s*(\d+)", text)
            if m_total:
                total = int(m_total.group(1) or m_total.group(2))
                pages = max(1, (total + items_this_page - 1) // items_this_page)
                log.info("  Pagination: %d items/page, ~%d total pages", items_this_page, pages)
                return pages

    # fallback เดิม
    for pat in [r"(\d[\d,]+)\s*รายการ"]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            total = int(m.group(1).replace(",", ""))
            return max(1, (total + per_page - 1) // per_page)
    return 1


def scrape_egp(config):
    """Fast path: plain HTTP requests"""
    filters   = config["search_filters"]
    d1, d2    = build_date_range(config)
    prov_map  = config["province_codes"]
    met_map   = config.get("method_codes", METHOD_MAP)
    prov_ids  = filters.get("province_ids", [""])
    met_ids   = filters.get("method_ids", ["1"])
    price_min = filters.get("price_min", 0)
    price_max = filters.get("price_max", "")
    per_page  = 20

    all_results = []
    session = requests.Session()

    for prov_id in prov_ids:
        prov_name = prov_map.get(str(prov_id), str(prov_id))
        for met_id in met_ids:
            met_name = met_map.get(str(met_id), str(met_id))
            log.info("Search: %s | %s | %s -> %s", prov_name, met_name, d1, d2)
            url = build_url(prov_id, met_id, price_min, price_max, d1, d2, 1, per_page)
            try:
                resp = session.get(url, headers=HEADERS, timeout=30)
                resp.raise_for_status()
                resp.encoding = "utf-8"
                if len(resp.text.strip()) < 200:
                    log.warning("Empty response - need Playwright")
                    return []
                soup = BeautifulSoup(resp.text, "html.parser")
            except Exception as e:
                log.warning("requests error: %s", e)
                return []

            pages = get_total_pages(soup, per_page)
            log.info("  Found %d page(s)", pages)
            all_results.extend(parse_results(soup, prov_name, met_name))

            for pg in range(2, min(pages + 1, 51)):
                time.sleep(1.5)
                try:
                    url = build_url(prov_id, met_id, price_min, price_max, d1, d2, pg, per_page)
                    resp = session.get(url, headers=HEADERS, timeout=30)
                    resp.encoding = "utf-8"
                    soup = BeautifulSoup(resp.text, "html.parser")
                    all_results.extend(parse_results(soup, prov_name, met_name))
                except Exception:
                    break

            time.sleep(2)

    log.info("[requests] Total: %d items", len(all_results))
    return all_results


def scrape_egp_playwright(config):
    """
    Playwright fallback for JS-rendered pages.
    Run once: playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        log.error("playwright not installed: pip install playwright")
        return []

    filters   = config["search_filters"]
    d1, d2    = build_date_range(config)
    prov_map  = config["province_codes"]
    met_map   = config.get("method_codes", METHOD_MAP)
    prov_ids  = filters.get("province_ids", [""])
    met_ids   = filters.get("method_ids", ["1"])
    price_min = filters.get("price_min", 0)
    price_max = filters.get("price_max", "")
    per_page  = 10   # Bug 2 Fix: e-GP แสดง 10 รายการ/หน้าจริง

    all_results = []
    seen_keys   = set()   # Bug 3 Fix: dedup ด้วย project key

    def add_unique(rows):
        """เพิ่มเฉพาะรายการที่ยังไม่มีใน seen_keys"""
        added = 0
        for r in rows:
            k = r.pop("_proj_key", r.get("ชื่อโครงการ", "")[:60])
            if k and k not in seen_keys:
                seen_keys.add(k)
                all_results.append(r)
                added += 1
            elif not k:
                all_results.append(r)  # ไม่มี key → ใส่ไปก่อน
        return added

    fetch_details = config.get("search_filters", {}).get("fetch_submission_date", False)

    def get_submission_date(detail_page):
        """
        ดึงวันที่ยื่นซองจาก detail page
        e-GP ใช้หลายชื่อ field: วันยื่นซอง / วันสิ้นสุดรับซอง / กำหนดยื่นซอง
        """
        text = detail_page.content()
        soup = BeautifulSoup(text, "html.parser")
        full_text = soup.get_text(separator=" ")

        date_patterns = [
            r"วันที่ยื่นซอง[^0-9]*(\d{1,2}/\d{1,2}/\d{4})",
            r"วันสิ้นสุดรับซอง[^0-9]*(\d{1,2}/\d{1,2}/\d{4})",
            r"กำหนดวันยื่นซอง[^0-9]*(\d{1,2}/\d{1,2}/\d{4})",
            r"กำหนดยื่น[^0-9]*(\d{1,2}/\d{1,2}/\d{4})",
            r"ยื่นซองวันที่[^0-9]*(\d{1,2}/\d{1,2}/\d{4})",
            r"ยื่นเสนอราคา[^0-9]*(\d{1,2}/\d{1,2}/\d{4})",
        ]
        for pat in date_patterns:
            m = re.search(pat, full_text)
            if m:
                return m.group(1)
        return ""

    def fetch_detail_for_rows(pw_page, rows, search_url):
        """
        คลิก link แต่ละโครงการใน list rows เพื่อดึงวันที่ยื่นซอง
        ใช้ index แทน stale element reference
        """
        for i, row in enumerate(rows):
            if row.get("วันที่ยื่นซอง"):
                continue  # มีแล้ว ข้ามไป

            proj_num = re.search(r"\d{11,}", row.get("ชื่อโครงการ", ""))
            if not proj_num:
                continue

            try:
                # navigate กลับไปหน้า search ก่อนคลิก (เผื่อ state หาย)
                pw_page.goto(search_url, wait_until="networkidle", timeout=20000)
                pw_page.wait_for_timeout(1000)

                # หา link ที่มี project number นี้ในข้อความ
                proj_id = proj_num.group(0)
                link_locator = pw_page.locator(
                    "table td a",
                    has_text=re.compile(proj_id)
                )
                if link_locator.count() == 0:
                    # ลอง locator แบบอื่น — บางครั้ง project id อยู่ใน parent td
                    link_locator = pw_page.locator(
                        "table td:has-text('" + proj_id + "') a"
                    )

                if link_locator.count() > 0:
                    link_locator.first.click()
                    pw_page.wait_for_load_state("networkidle", timeout=15000)
                    pw_page.wait_for_timeout(1000)
                    date = get_submission_date(pw_page)
                    row["วันที่ยื่นซอง"] = date
                    log.info("  [detail] %s → %s", proj_id, date or "(ไม่พบ)")
                    pw_page.go_back(wait_until="networkidle", timeout=15000)
                    pw_page.wait_for_timeout(800)

            except Exception as e:
                log.warning("  [detail] error project %s: %s", proj_num.group(0) if proj_num else "?", e)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx     = browser.new_context(user_agent=HEADERS["User-Agent"], locale="th-TH")
        page    = ctx.new_page()

        for prov_id in prov_ids:
            prov_name = prov_map.get(str(prov_id), str(prov_id))
            for met_id in met_ids:
                met_name = met_map.get(str(met_id), str(met_id))
                log.info("[PW] Search: %s | %s", prov_name, met_name)

                page_rows_by_url = {}   # เก็บ rows ของแต่ละหน้า สำหรับ detail fetching

                for pg in range(1, 51):
                    search_url = build_url(prov_id, met_id, price_min, price_max, d1, d2, pg, per_page)
                    try:
                        page.goto(search_url, wait_until="networkidle", timeout=30000)
                        page.wait_for_timeout(1500 if pg > 1 else 2000)
                    except PWTimeout:
                        log.warning("[PW] timeout page %d", pg)
                        break

                    soup = BeautifulSoup(page.content(), "html.parser")
                    if pg == 1:
                        total_pages = get_total_pages(soup, per_page)
                        log.info("  Found ~%d page(s)", total_pages)

                    new_rows = parse_results(soup, prov_name, met_name)

                    # ดึง detail ถ้าเปิดใช้งาน
                    if fetch_details and new_rows:
                        log.info("  Fetching detail for %d items (page %d)...", len(new_rows), pg)
                        fetch_detail_for_rows(page, new_rows, search_url)

                    n = add_unique(new_rows)
                    log.info("  Page %d: +%d unique items", pg, n)

                    if n == 0:
                        log.info("  No new items — stopping")
                        break
                    if pg >= total_pages:
                        break

        browser.close()

    log.info("[Playwright] Total unique: %d items", len(all_results))
    return all_results


if __name__ == "__main__":
    cfg  = load_config()
    data = scrape_egp(cfg)
    if not data:
        log.info("Trying Playwright...")
        data = scrape_egp_playwright(cfg)
    print("\nTotal: %d items" % len(data))
    for row in data[:3]:
        print(row)
