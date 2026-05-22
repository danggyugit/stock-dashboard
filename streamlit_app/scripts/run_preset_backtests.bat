@echo off
REM ====================================================================
REM  Daily preset backtests runner.
REM
REM  Runs 3 IT-sector backtests (Inv-Vol / Equal / Inv-Vol+Regime)
REM  and saves results to data/cache/backtests/{preset}.json.
REM
REM  Schedule via Windows Task Scheduler:
REM    Daily at 11:00 KST
REM
REM  Setup:
REM    Run as Administrator:
REM    powershell -File scripts\register_scheduler_preset_backtests.ps1
REM ====================================================================

setlocal enabledelayedexpansion
set "REPO=c:\Users\sk15y\claude\stock_dashboard"
set "LOG=%REPO%\streamlit_app\scripts\preset_backtests.log"

echo [%date% %time%] === Starting preset backtests === >> "%LOG%"

cd /d "%REPO%" || (
    echo [%date% %time%] ERROR: failed to cd into repo >> "%LOG%"
    exit /b 1
)

echo [%date% %time%] Running run_preset_backtests.py >> "%LOG%"
cd /d "%REPO%\streamlit_app"
"C:\Python\python.exe" scripts\run_preset_backtests.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: run_preset_backtests.py failed >> "%LOG%"
    exit /b 1
)

cd /d "%REPO%" || exit /b 1

echo [%date% %time%] git add backtests/ >> "%LOG%"
git add streamlit_app/data/cache/backtests/ >> "%LOG%" 2>&1

git diff --staged --quiet
if errorlevel 1 (
    echo [%date% %time%] Committing changes >> "%LOG%"
    git commit -m "chore: refresh preset backtests (local scheduler)" >> "%LOG%" 2>&1

    REM ── Push with up to 3 merge-and-retry attempts.
    REM    Use "ours" merge strategy to bypass CON.json Windows issue
    REM    (remote cache-update commits include valuation/CON.json which
    REM     Windows cannot checkout).
    set "PUSH_OK=0"
    for /L %%i in (1,1,3) do (
        if "!PUSH_OK!"=="0" (
            git push origin main >> "%LOG%" 2>&1
            if not errorlevel 1 (
                set "PUSH_OK=1"
            ) else (
                echo [%date% %time%] Push attempt %%i failed - fetch+merge ours and retry >> "%LOG%"
                git fetch origin >> "%LOG%" 2>&1
                git merge -s ours origin/main --no-edit -m "Merge remote cache history (ours - bypass CON.json)" >> "%LOG%" 2>&1
            )
        )
    )
    if "!PUSH_OK!"=="0" (
        echo [%date% %time%] ERROR: git push failed after 3 retries >> "%LOG%"
        exit /b 1
    )
    echo [%date% %time%] === Pushed successfully === >> "%LOG%"
) else (
    echo [%date% %time%] No changes to commit >> "%LOG%"
)

endlocal
exit /b 0
