@echo off
echo ============================================
echo  ระบบตรวจสอบประมูลภาครัฐ e-GP
echo ============================================

cd /d "%~dp0"

echo รันแบบ Playwright (รองรับ JavaScript)...
python main.py --playwright --mode append

echo.
echo ============================================
if errorlevel 0 (
    echo  ✅ เสร็จสิ้น! ดูผลใน Google Sheet
) else (
    echo  ❌ เกิดข้อผิดพลาด ดู log ด้านบน
)
echo ============================================
pause
