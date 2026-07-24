@echo off
setlocal enabledelayedexpansion
set "REPO=c:\Users\sk15y\claude\stock_dashboard"
set "APP=%REPO%\streamlit_app"
set "LOG=%APP%\scripts\sec_intelligence.log"

echo [%date% %time%] === SEC Intelligence START === >> "%LOG%"

cd /d "%APP%"
if errorlevel 1 (
    echo [%date% %time%] ERROR: cd failed >> "%LOG%"
    exit /b 1
)

cd /d "%REPO%"
git fetch origin >> "%LOG%" 2>&1
git merge origin/main --no-edit >> "%LOG%" 2>&1
cd /d "%APP%"

echo [%date% %time%] Running fetch_sec_intelligence.py >> "%LOG%"
"C:\Python\python.exe" scripts\fetch_sec_intelligence.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: script failed >> "%LOG%"
    exit /b 1
)

echo [%date% %time%] === SEC Intelligence DONE === >> "%LOG%"
endlocal
exit /b 0