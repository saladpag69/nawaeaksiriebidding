# -*- coding: utf-8 -*-
"""
Web UI สำหรับระบบประมูลภาครัฐ
รัน: python web_app.py
เปิด: http://localhost:5000
"""

import csv
import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, request, url_for # type: ignore

BASE_DIR    = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# เขียน credentials.json จาก env var (สำหรับ Railway)
_creds_env = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if _creds_env:
    with open(BASE_DIR / "credentials.json", "w", encoding="utf-8") as _f:
        _f.write(_creds_env)

app = Flask(__name__)

# custom Jinja filter: ดึง project number จากข้อความ
import re as _re
@app.template_filter("regex_search")
def regex_search_filter(s, pattern):
    m = _re.search(pattern, s or "")
    return m.group(0) if m else ""

# --- global run state ---
run_state = {"running": False, "log": [], "last_run": ""}


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_config(data: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_latest_csv():
    csvs = sorted(RESULTS_DIR.glob("procurement_*.csv"), reverse=True)
    if not csvs:
        return [], []
    with open(csvs[0], encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames or []
    return headers, rows


# ─────────────────────────── TEMPLATES ──────────────────────────────

BASE_HTML = """
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ระบบประมูลภาครัฐ</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #f0f4f8; color: #222; }
  nav { background: #1a3a5c; color: #fff; padding: 14px 24px;
        display: flex; align-items: center; gap: 24px; }
  nav a { color: #a8d4ff; text-decoration: none; font-size: 15px; }
  nav a:hover, nav a.active { color: #fff; border-bottom: 2px solid #fff; }
  nav .brand { font-size: 18px; font-weight: 700; color: #fff; margin-right: 16px; }
  .container { max-width: 1200px; margin: 28px auto; padding: 0 20px; }
  .card { background: #fff; border-radius: 10px; padding: 24px;
          box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 20px; }
  h2 { font-size: 18px; margin-bottom: 16px; color: #1a3a5c; }
  label { display: block; font-size: 14px; margin-bottom: 4px; color: #555; }
  input[type=text], input[type=number], select {
    width: 100%; padding: 8px 12px; border: 1px solid #ccc;
    border-radius: 6px; font-size: 14px; margin-bottom: 12px; }
  .row { display: flex; gap: 16px; flex-wrap: wrap; }
  .col { flex: 1; min-width: 140px; }
  .btn { padding: 10px 22px; border: none; border-radius: 6px;
         cursor: pointer; font-size: 14px; font-weight: 600; }
  .btn-primary { background: #1a3a5c; color: #fff; }
  .btn-success { background: #22863a; color: #fff; }
  .btn-warning { background: #d97706; color: #fff; }
  .btn:disabled { opacity: .5; cursor: not-allowed; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px;
           font-size: 12px; font-weight: 600; }
  .badge-green { background: #dcfce7; color: #166534; }
  .badge-blue  { background: #dbeafe; color: #1e40af; }
  .badge-red   { background: #fee2e2; color: #991b1b; }
  .badge-gray  { background: #f1f5f9; color: #475569; }
  #log-box { background: #0f172a; color: #94a3b8; font-family: monospace;
             font-size: 13px; padding: 16px; border-radius: 8px;
             height: 220px; overflow-y: auto; white-space: pre-wrap; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: #1a3a5c; color: #fff; padding: 10px 12px; text-align: left;
       position: sticky; top: 0; }
  td { padding: 8px 12px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
  tr:hover td { background: #f8fafc; }
  .tbl-wrap { overflow-x: auto; max-height: 70vh; }
  .stat-bar { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }
  .stat { background: #fff; border-radius: 8px; padding: 14px 20px;
          box-shadow: 0 1px 4px rgba(0,0,0,.07); min-width: 130px; }
  .stat .val { font-size: 28px; font-weight: 700; color: #1a3a5c; }
  .stat .lbl { font-size: 12px; color: #888; margin-top: 2px; }
  .toggle { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
  .toggle input[type=checkbox] { width: 18px; height: 18px; cursor: pointer; }
  .tag { display: inline-block; background: #e0f2fe; color: #0369a1;
         border-radius: 4px; padding: 2px 8px; font-size: 12px; margin: 2px; }
  .filter-bar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
                margin-bottom: 16px; }
  .filter-bar input, .filter-bar select { margin: 0; width: auto; flex: 1; min-width: 160px; }
  .running-dot { width: 10px; height: 10px; background: #22c55e;
                 border-radius: 50%; display: inline-block;
                 animation: pulse 1s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
  .proj-name { min-width: 360px; max-width: 600px; }
  .proj-name span { font-size: 13px; white-space: normal; }
</style>
</head>
<body>
<nav>
  <span class="brand">🏛 ระบบประมูลภาครัฐ</span>
  <a href="/" class="{{ 'active' if page=='settings' else '' }}">⚙️ ตั้งค่า & รัน</a>
  <a href="/results" class="{{ 'active' if page=='results' else '' }}">📊 ผลการค้นหา</a>
</nav>
<div class="container">
  {% block content %}{% endblock %}
</div>
<script>
function fmt(n){ return n?.toString().replace(/\B(?=(\d{3})+(?!\d))/g,',') || n; }
</script>
</body>
</html>
"""

SETTINGS_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="card">
  <h2>⚙️ ตั้งค่าการค้นหา</h2>
  <form id="cfg-form" method="POST" action="/save_config">

    <div class="row">
      <div class="col">
        <label>จังหวัด (moiId คั่นด้วย ,)</label>
        <input type="text" name="province_ids" value="{{ cfg.search_filters.province_ids | join(',') }}"
               placeholder="140000,190000">
      </div>
      <div class="col">
        <label>วิธีการจัดหา</label>
        <select name="method_ids" multiple style="height:90px">
          <option value="16" {{ 'selected' if '16' in cfg.search_filters.method_ids }}>e-Bidding</option>
          <option value="15" {{ 'selected' if '15' in cfg.search_filters.method_ids }}>e-Market</option>
          <option value="18" {{ 'selected' if '18' in cfg.search_filters.method_ids }}>คัดเลือก</option>
          <option value="19" {{ 'selected' if '19' in cfg.search_filters.method_ids }}>เฉพาะเจาะจง</option>
        </select>
      </div>
    </div>

    <div class="row">
      <div class="col">
        <label>ย้อนหลัง (วัน)</label>
        <input type="number" name="days_behind" value="{{ cfg.search_filters.days_behind }}" min="0" max="365">
      </div>
      <div class="col">
        <label>ล่วงหน้า (วัน)</label>
        <input type="number" name="days_ahead" value="{{ cfg.search_filters.days_ahead }}" min="0" max="365">
      </div>
      <div class="col">
        <label>มูลค่าขั้นต่ำ (บาท)</label>
        <input type="number" name="price_min" value="{{ cfg.search_filters.price_min }}" min="0">
      </div>
      <div class="col">
        <label>มูลค่าสูงสุด (บาท)</label>
        <input type="number" name="price_max" value="{{ cfg.search_filters.price_max }}" min="0">
      </div>
    </div>

    <div class="row">
      <div class="col">
        <label>วันที่เริ่มต้น (ว/ด/ปปปป) — เว้นว่างใช้อัตโนมัติ</label>
        <input type="text" name="date_start" value="{{ cfg.search_filters.date_start }}" placeholder="01/05/2026">
      </div>
      <div class="col">
        <label>วันที่สิ้นสุด</label>
        <input type="text" name="date_end" value="{{ cfg.search_filters.date_end }}" placeholder="31/05/2026">
      </div>
    </div>

    <div class="toggle">
      <input type="checkbox" name="fetch_submission_date" id="fsd"
             {{ 'checked' if cfg.search_filters.get('fetch_submission_date') }}>
      <label for="fsd" style="margin:0;cursor:pointer">
        ดึงวันที่ยื่นซองจาก detail page (ช้าลง ~2-3 นาที)
      </label>
    </div>

    <button type="submit" class="btn btn-primary">💾 บันทึก config</button>
  </form>
</div>

<div class="card">
  <h2>🚀 รันการค้นหา</h2>
  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
    <button class="btn btn-success" id="btn-run" onclick="startRun()" {{ 'disabled' if running }}>
      {{ '⏳ กำลังรัน...' if running else '▶️ รันเดี๋ยวนี้' }}
    </button>
    <button class="btn btn-warning" onclick="location.href='/results'">📊 ดูผลล่าสุด</button>
    {% if running %}
    <span><span class="running-dot"></span> กำลังทำงาน...</span>
    {% endif %}
    {% if last_run %}
    <span style="color:#666;font-size:13px">รันล่าสุด: {{ last_run }}</span>
    {% endif %}
  </div>
  <div id="log-box" style="margin-top:16px">{{ log_text }}</div>
</div>

<script>
function startRun(){
  document.getElementById('btn-run').disabled = true;
  document.getElementById('btn-run').innerText = '⏳ กำลังรัน...';
  fetch('/run', {method:'POST'}).then(r=>r.json()).then(d=>{
    if(d.status==='started') pollLog();
  });
}
function pollLog(){
  fetch('/log').then(r=>r.json()).then(d=>{
    document.getElementById('log-box').innerText = d.log;
    document.getElementById('log-box').scrollTop = 9999;
    if(d.running){
      setTimeout(pollLog, 1500);
    } else {
      document.getElementById('btn-run').disabled = false;
      document.getElementById('btn-run').innerText = '▶️ รันเดี๋ยวนี้';
    }
  });
}
{% if running %} pollLog(); {% endif %}
</script>
""")

RESULTS_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="stat-bar">
  <div class="stat"><div class="val">{{ total }}</div><div class="lbl">รายการทั้งหมด</div></div>
  <div class="stat"><div class="val">{{ provinces }}</div><div class="lbl">จังหวัด</div></div>
  <div class="stat"><div class="val">{{ files }}</div><div class="lbl">ไฟล์ CSV</div></div>
  <div class="stat"><div class="val">{{ latest_date }}</div><div class="lbl">ค้นหาล่าสุด</div></div>
</div>

<div class="card">
  <div class="filter-bar">
    <input type="text" id="q" placeholder="🔍 ค้นหา ชื่อโครงการ / หน่วยงาน..." oninput="filterTable()">
    <select id="fProv" onchange="filterTable()">
      <option value="">-- จังหวัดทั้งหมด --</option>
      {% for p in prov_list %}
      <option value="{{ p }}">{{ p }}</option>
      {% endfor %}
    </select>
    <select id="fMethod" onchange="filterTable()">
      <option value="">-- วิธีทั้งหมด --</option>
      {% for m in method_list %}
      <option value="{{ m }}">{{ m }}</option>
      {% endfor %}
    </select>
    <select id="fStatus" onchange="filterTable()">
      <option value="">-- สถานะทั้งหมด --</option>
      {% for s in status_list %}
      <option value="{{ s }}">{{ s }}</option>
      {% endfor %}
    </select>
    <button class="btn btn-primary" onclick="exportCSV()">⬇️ Export</button>
  </div>

  {% if headers %}
  <div class="tbl-wrap">
    <table id="tbl">
      <thead>
        <tr>
          {% for h in headers %}
          <th onclick="sortTable({{ loop.index0 }})" style="cursor:pointer;user-select:none;
              {% if h == 'ชื่อโครงการ' %}min-width:320px{% endif %}">
            {{ h }} ⇅
          </th>
          {% endfor %}
          <th style="background:#1a3a5c;color:#fff;padding:10px 12px;min-width:90px">เอกสาร</th>
        </tr>
      </thead>
      <tbody>
        {% for row in rows %}
        {% set proj_title = row.get('ชื่อโครงการ','') %}
        {% set proj_num = proj_title | regex_search('\\d{11,}') %}
        <tr data-prov="{{ row.get('จังหวัด','') }}"
            data-method="{{ row.get('วิธีการจัดหา','') }}"
            data-status="{{ row.get('สถานะ','') }}"
            data-proj="{{ proj_num or '' }}">
          {% for h in headers %}
          <td{% if h == 'ชื่อโครงการ' %} class="proj-name"{% endif %}>
            {% if h == 'ลิงก์' and row[h] %}
              <a href="{{ row[h] }}" target="_blank" class="badge badge-blue">🔗 เปิด</a>
            {% elif h == 'สถานะ' %}
              {% if 'ยกเลิก' in row[h] %}
                <span class="badge badge-red">{{ row[h] }}</span>
              {% elif 'ระหว่าง' in row[h] %}
                <span class="badge badge-green">{{ row[h] }}</span>
              {% else %}
                <span class="badge badge-gray">{{ row[h] }}</span>
              {% endif %}
            {% elif h == 'วงเงินงบประมาณ' %}
              <span style="font-weight:700;color:#1a3a5c">{{ row[h] }}</span>
            {% elif h == 'ชื่อโครงการ' %}
              <span style="display:block;line-height:1.6;word-break:break-word">{{ row[h] }}</span>
            {% elif h == 'วันที่ยื่นซอง' and row[h] %}
              <span style="color:#d97706;font-weight:600">📅 {{ row[h] }}</span>
            {% else %}
              {{ row[h] }}
            {% endif %}
          </td>
          {% endfor %}
          {# ปุ่มเอกสาร — ดึง project number จาก data-proj #}
          <td style="white-space:nowrap;vertical-align:middle">
            {% if proj_num %}
              <a href="https://process3.gprocurement.go.th/egp2procmainWeb/procsearch.sch?homeflag=A&proc_id=FPRO9965&servlet=FPRO9965Servlet&projectId={{ proj_num }}&announceType=2"
                 target="_blank" class="badge badge-blue" title="ดูประกาศทั้งหมดของโครงการนี้">
                📄 ประกาศ
              </a><br><br>
              <a href="https://process3.gprocurement.go.th/egp2procmainWeb/procsearch.sch?homeflag=A&proc_id=FPRO9965&servlet=FPRO9965Servlet&projectId={{ proj_num }}&announceType=15"
                 target="_blank" class="badge badge-gray" title="ดูประกาศราคากลาง">
                💰 ราคากลาง
              </a>
            {% else %}
              <span style="color:#ccc;font-size:12px">—</span>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <p style="color:#888;text-align:center;padding:40px">
    ยังไม่มีข้อมูล — กด ▶️ รัน จากหน้า ตั้งค่า
  </p>
  {% endif %}
</div>

<script>
let sortDir = {};
function filterTable(){
  const q  = document.getElementById('q').value.toLowerCase();
  const fp = document.getElementById('fProv').value;
  const fm = document.getElementById('fMethod').value;
  const fs = document.getElementById('fStatus').value;
  const rows = document.querySelectorAll('#tbl tbody tr');
  rows.forEach(tr => {
    const txt    = tr.innerText.toLowerCase();
    const prov   = tr.dataset.prov   || '';
    const method = tr.dataset.method || '';
    const status = tr.dataset.status || '';
    const show = (!q || txt.includes(q))
              && (!fp || prov.includes(fp))
              && (!fm || method.includes(fm))
              && (!fs || status.includes(fs));
    tr.style.display = show ? '' : 'none';
  });
}

function sortTable(col){
  const tbl = document.getElementById('tbl');
  const tbody = tbl.querySelector('tbody');
  const rows = [...tbody.querySelectorAll('tr')];
  sortDir[col] = !sortDir[col];
  rows.sort((a,b) => {
    const x = a.querySelectorAll('td')[col]?.innerText || '';
    const y = b.querySelectorAll('td')[col]?.innerText || '';
    const nx = parseFloat(x.replace(/[^0-9.]/g,'')), ny = parseFloat(y.replace(/[^0-9.]/g,''));
    if(!isNaN(nx)&&!isNaN(ny)) return sortDir[col]?(nx-ny):(ny-nx);
    return sortDir[col]?x.localeCompare(y,'th'):y.localeCompare(x,'th');
  });
  rows.forEach(r => tbody.appendChild(r));
}

function exportCSV(){
  const rows = [...document.querySelectorAll('#tbl tr')];
  const csv = rows.filter(r=>r.style.display!=='none')
    .map(r => [...r.querySelectorAll('th,td')]
      .map(c => '"'+c.innerText.replace(/"/g,'""')+'"').join(','))
    .join('\\n');
  const a = document.createElement('a');
  a.href = 'data:text/csv;charset=utf-8,\\uFEFF'+encodeURIComponent(csv);
  a.download = 'procurement_export.csv';
  a.click();
}
</script>
""")

# ─────────────────────────── ROUTES ──────────────────────────────

@app.route("/")
def settings():
    cfg = load_config()
    return render_template_string(
        SETTINGS_HTML,
        page="settings",
        cfg=cfg,
        running=run_state["running"],
        log_text="\n".join(run_state["log"][-60:]),
        last_run=run_state["last_run"],
    )


@app.route("/save_config", methods=["POST"])
def save_config_route():
    cfg = load_config()
    f = request.form

    cfg["search_filters"]["province_ids"] = [
        x.strip() for x in f.get("province_ids", "").split(",") if x.strip()
    ]
    cfg["search_filters"]["method_ids"] = f.getlist("method_ids") or ["16"]
    cfg["search_filters"]["days_behind"]  = int(f.get("days_behind", 30))
    cfg["search_filters"]["days_ahead"]   = int(f.get("days_ahead", 0))
    cfg["search_filters"]["price_min"]    = int(f.get("price_min", 0))
    cfg["search_filters"]["price_max"]    = int(f.get("price_max", 100000000))
    cfg["search_filters"]["date_start"]   = f.get("date_start", "").strip()
    cfg["search_filters"]["date_end"]     = f.get("date_end", "").strip()
    cfg["search_filters"]["fetch_submission_date"] = "fetch_submission_date" in f

    save_config(cfg)
    return redirect(url_for("settings"))


@app.route("/run", methods=["POST"])
def run_scraper():
    if run_state["running"]:
        return jsonify({"status": "already_running"})

    def do_run():
        run_state["running"] = True
        run_state["log"] = ["[START] " + datetime.now().strftime("%d/%m/%Y %H:%M:%S")]
        try:
            proc = subprocess.Popen(
                [sys.executable, str(BASE_DIR / "main.py"), "--playwright", "--mode", "append"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR),
                encoding="utf-8",
                errors="replace",
            )
            for line in proc.stdout:
                run_state["log"].append(line.rstrip())
                if len(run_state["log"]) > 500:
                    run_state["log"] = run_state["log"][-400:]
            proc.wait()
            run_state["log"].append("[DONE] exit code: " + str(proc.returncode))
        except Exception as e:
            run_state["log"].append("[ERROR] " + str(e))
        finally:
            run_state["running"] = False
            run_state["last_run"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    threading.Thread(target=do_run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/log")
def get_log():
    return jsonify({
        "running": run_state["running"],
        "log": "\n".join(run_state["log"][-80:]),
    })


HIDDEN_COLS = {"วันที่ค้นหา", "วิธีการจัดหา", "ลำดับ"}


@app.route("/results")
def results():
    headers, rows = load_latest_csv()
    csv_count = len(list(RESULTS_DIR.glob("procurement_*.csv")))

    # กรอง column ที่ไม่ต้องการแสดง
    headers = [h for h in headers if h not in HIDDEN_COLS]

    prov_set   = sorted({r.get("จังหวัด", "") for r in rows if r.get("จังหวัด")})
    method_set = sorted({r.get("วิธีการจัดหา", "") for r in rows if r.get("วิธีการจัดหา")})
    status_set = sorted({r.get("สถานะ", "") for r in rows if r.get("สถานะ")})
    latest_d   = rows[0].get("วันที่ค้นหา", "-")[:10] if rows else "-"

    return render_template_string(
        RESULTS_HTML,
        page="results",
        headers=headers,
        rows=rows,
        total=len(rows),
        provinces=len(prov_set),
        files=csv_count,
        latest_date=latest_d,
        prov_list=prov_set,
        method_list=method_set,
        status_list=status_set,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "="*50)
    print("  ระบบประมูลภาครัฐ — Web UI")
    print(f"  เปิด: http://localhost:{port}")
    print("="*50 + "\n")
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
