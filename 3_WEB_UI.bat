@echo off
echo ============================================
echo  ระบบประมูลภาครัฐ — Web UI
echo ============================================
cd /d "%~dp0"

pip install flask --quiet

echo.
echo เปิดเบราว์เซอร์: http://localhost:5000
echo กด Ctrl+C เพื่อหยุด
echo.

start "" "http://localhost:5000"
python web_app.py
pause
