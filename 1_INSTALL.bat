@echo off
echo ============================================
echo  ติดตั้ง dependencies สำหรับระบบประมูลรัฐ
echo ============================================

echo.
echo [1/3] ติดตั้ง Python packages...
pip install requests beautifulsoup4 lxml gspread google-auth playwright
if errorlevel 1 (
    echo ❌ pip install ล้มเหลว กรุณาตรวจสอบ Python
    pause
    exit /b 1
)

echo.
echo [2/3] ติดตั้ง Playwright Chromium browser...
playwright install chromium
if errorlevel 1 (
    echo ❌ playwright install ล้มเหลว ลองรันใหม่อีกครั้ง
    pause
    exit /b 1
)

echo.
echo [3/3] ตรวจสอบ...
python -c "import requests, bs4, gspread, playwright; print('✅ ทุก package พร้อมใช้')"

echo.
echo ============================================
echo  ✅ ติดตั้งสำเร็จ!
echo  ขั้นตอนถัดไป: ดู README_SETUP.md
echo  แล้วรัน: 2_RUN.bat
echo ============================================
pause
