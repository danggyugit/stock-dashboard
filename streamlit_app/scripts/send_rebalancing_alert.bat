@echo off
REM ====================================================================
REM  Monthly rebalancing alert sender.
REM  Schedule: Monthly on 1st day at 11:30 KST via Windows Task Scheduler
REM  Reads cached preset backtest JSONs and sends today_picks via Telegram.
REM ====================================================================

setlocal enabledelayedexpansion
set "REPO=c:\Users\sk15y\claude\stock_dashboard"
set "LOG=%REPO%\streamlit_app\scripts\rebalancing_alert.log"

echo [%date% %time%] === Starting rebalancing alert === >> "%LOG%"

cd /d "%REPO%\streamlit_app" || (
    echo [%date% %time%] ERROR: failed to cd into repo >> "%LOG%"
    exit /b 1
)

"C:\Python\python.exe" scripts\send_rebalancing_alert.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: send_rebalancing_alert.py failed >> "%LOG%"
    exit /b 1
)

echo [%date% %time%] === Done === >> "%LOG%"
endlocal
exit /b 0