@echo off
setlocal
set "APP=c:\Users\sk15y\claude\stock_dashboard\streamlit_app"
set "LOG=%APP%\scripts\portfolio_risk_alert.log"
echo [%date% %time%] === Portfolio Risk Alert START === >> "%LOG%"
cd /d "%APP%"
"C:\Python\python.exe" scripts\portfolio_risk_alert.py >> "%LOG%" 2>&1
echo [%date% %time%] === DONE (exit %errorlevel%) === >> "%LOG%"
endlocal
exit /b 0
