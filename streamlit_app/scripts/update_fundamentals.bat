@echo off
REM ====================================================================
REM  Local fundamentals refresh — runs from a residential IP to bypass
REM  yfinance's data center IP blocks. Schedule weekly via Windows Task
REM  Scheduler (e.g. Sundays 03:00).
REM
REM  Setup:
REM    1. Win + R -> taskschd.msc
REM    2. Create Basic Task -> Weekly -> Sunday 03:00
REM    3. Action: Start a program
REM    4. Program: c:\Users\sk15y\claude\stock_dashboard\streamlit_app\scripts\update_fundamentals.bat
REM    5. Check "Run whether user is logged on or not" + "Run with highest privileges"
REM ====================================================================

setlocal
set "REPO=c:\Users\sk15y\claude\stock_dashboard"
set "LOG=%REPO%\streamlit_app\scripts\update_fundamentals.log"

echo [%date% %time%] === Starting fundamentals refresh === >> "%LOG%"

cd /d "%REPO%\streamlit_app" || (
    echo [%date% %time%] ERROR: failed to cd into repo >> "%LOG%"
    exit /b 1
)

echo [%date% %time%] Running fetch_cache.py --fundamentals-all (S^&P 1500) >> "%LOG%"
python scripts\fetch_cache.py --fundamentals-all >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: fetch_cache.py failed >> "%LOG%"
    exit /b 1
)

cd /d "%REPO%" || exit /b 1

echo [%date% %time%] git add fundamentals.json + meta.json >> "%LOG%"
git add streamlit_app/data/cache/fundamentals.json streamlit_app/data/cache/meta.json >> "%LOG%" 2>&1

REM Skip commit if no changes
git diff --staged --quiet
if errorlevel 1 (
    echo [%date% %time%] Committing changes >> "%LOG%"
    git commit -m "chore: refresh fundamentals (local cron)" >> "%LOG%" 2>&1
    git push origin main >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo [%date% %time%] ERROR: git push failed >> "%LOG%"
        exit /b 1
    )
    echo [%date% %time%] === Pushed successfully === >> "%LOG%"
) else (
    echo [%date% %time%] No changes to commit >> "%LOG%"
)

endlocal
exit /b 0
