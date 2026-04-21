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
set "STASH_MSG=preset-scheduler-auto-stash"
set "STASHED=0"

echo [%date% %time%] === Starting preset backtests === >> "%LOG%"

cd /d "%REPO%" || (
    echo [%date% %time%] ERROR: failed to cd into repo >> "%LOG%"
    exit /b 1
)

REM ── Stash any unstaged / untracked changes so pull --rebase won't fail.
REM    -u: include untracked files. Stash message checked afterwards to
REM    know whether anything was actually stashed.
git stash push -u -m "%STASH_MSG%" >> "%LOG%" 2>&1
git stash list | findstr /C:"%STASH_MSG%" >nul
if not errorlevel 1 set "STASHED=1"

REM ── Pull latest to avoid push conflicts later.
git pull --rebase -X ours origin main >> "%LOG%" 2>&1

cd /d "%REPO%\streamlit_app"

echo [%date% %time%] Running run_preset_backtests.py >> "%LOG%"
"C:\Python\python.exe" scripts\run_preset_backtests.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: run_preset_backtests.py failed >> "%LOG%"
    call :restore_stash
    exit /b 1
)

cd /d "%REPO%" || (
    call :restore_stash
    exit /b 1
)

echo [%date% %time%] git add backtests/ >> "%LOG%"
git add streamlit_app/data/cache/backtests/ >> "%LOG%" 2>&1

git diff --staged --quiet
if errorlevel 1 (
    echo [%date% %time%] Committing changes >> "%LOG%"
    git commit -m "chore: refresh preset backtests (local scheduler)" >> "%LOG%" 2>&1

    REM ── Push with up to 3 rebase-retry attempts.
    set "PUSH_OK=0"
    for /L %%i in (1,1,3) do (
        if "!PUSH_OK!"=="0" (
            git push origin main >> "%LOG%" 2>&1
            if not errorlevel 1 (
                set "PUSH_OK=1"
            ) else (
                echo [%date% %time%] Push attempt %%i failed - pull rebase and retry >> "%LOG%"
                git pull --rebase -X ours origin main >> "%LOG%" 2>&1
            )
        )
    )
    if "!PUSH_OK!"=="0" (
        echo [%date% %time%] ERROR: git push failed after 3 retries >> "%LOG%"
        call :restore_stash
        exit /b 1
    )
    echo [%date% %time%] === Pushed successfully === >> "%LOG%"
) else (
    echo [%date% %time%] No changes to commit >> "%LOG%"
)

call :restore_stash
endlocal
exit /b 0


:restore_stash
REM Pop the auto-stash if we created one. Safe to call even if unset.
if "!STASHED!"=="1" (
    echo [%date% %time%] Restoring stashed changes >> "%LOG%"
    git stash pop >> "%LOG%" 2>&1
)
goto :eof
