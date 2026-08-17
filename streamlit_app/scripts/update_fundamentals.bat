@echo off
REM ====================================================================
REM  Local fundamentals refresh — runs from a residential IP to bypass
REM  yfinance's data-center IP blocks.
REM
REM  Uses --fundamentals-all --merge:
REM    - Fetches all S&P 1500 tickers sequentially (0.5s delay)
REM    - Merges into existing fundamentals.json (partial success OK)
REM    - Pushes to GitHub → Streamlit Cloud picks up automatically
REM
REM  Schedule via Windows Task Scheduler:
REM    Daily at 13:00 KST
REM
REM  Setup:
REM    Run as Administrator:
REM    powershell -File scripts\register_scheduler_daily.ps1
REM ====================================================================

setlocal
set "REPO=c:\Users\sk15y\claude\stock_dashboard"
set "LOG=%REPO%\streamlit_app\scripts\update_fundamentals.log"

echo [%date% %time%] === Starting fundamentals refresh === >> "%LOG%"

cd /d "%REPO%\streamlit_app" || (
    echo [%date% %time%] ERROR: failed to cd into repo >> "%LOG%"
    exit /b 1
)

REM Pull latest to avoid push conflicts
cd /d "%REPO%"
git pull --rebase origin main >> "%LOG%" 2>&1
cd /d "%REPO%\streamlit_app"

REM Step 1: prices/heatmap refresh (no flags = stocks.json + heatmap only).
REM Separate process from fundamentals so the batch yf.download() session
REM does not contaminate the per-ticker .info calls with rate limits.
echo [%date% %time%] Running fetch_cache.py (prices/heatmap) >> "%LOG%"
python scripts\fetch_cache.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] WARNING: prices/heatmap fetch failed - continuing to fundamentals >> "%LOG%"
)

REM Step 2: fundamentals refresh (full 1500, incremental merge)
echo [%date% %time%] Running fetch_cache.py --fundamentals-only --merge >> "%LOG%"
python scripts\fetch_cache.py --fundamentals-only --merge >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: fetch_cache.py failed >> "%LOG%"
    exit /b 1
)

cd /d "%REPO%" || exit /b 1

echo [%date% %time%] git add cache (fundamentals + heatmap + stocks + meta) >> "%LOG%"
git add streamlit_app/data/cache/fundamentals.json streamlit_app/data/cache/heatmap.json streamlit_app/data/cache/stocks.json streamlit_app/data/cache/meta.json streamlit_app/data/cache/market_snapshot.json >> "%LOG%" 2>&1

REM Skip commit if no changes
git diff --staged --quiet
if errorlevel 1 (
    echo [%date% %time%] Committing changes >> "%LOG%"
    git commit -m "chore: refresh price + fundamentals cache (local scheduler)" >> "%LOG%" 2>&1
    git push origin main >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo [%date% %time%] Initial push failed — pull rebase + retry >> "%LOG%"
        git pull --rebase -X ours origin main >> "%LOG%" 2>&1
        git push origin main >> "%LOG%" 2>&1
        if errorlevel 1 (
            echo [%date% %time%] ERROR: git push failed after retry >> "%LOG%"
            exit /b 1
        )
    )
    echo [%date% %time%] === Pushed successfully === >> "%LOG%"
) else (
    echo [%date% %time%] No changes to commit >> "%LOG%"
)

endlocal
exit /b 0
