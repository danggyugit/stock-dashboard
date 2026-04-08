# =====================================================================
#  Register a ONE-SHOT scheduled task that runs the fundamentals
#  refresh ~65 minutes from when this script was generated. Lets the
#  yfinance rate-limit cool down before the first fetch.
#
#  Run this once from PowerShell (no admin needed for one-shot user task):
#     powershell -ExecutionPolicy Bypass -File register_scheduler_oneshot.ps1
#
#  After it runs, the task is auto-disabled but stays in the list. To
#  remove it manually:
#     Unregister-ScheduledTask -TaskName "StockDashboard-Fundamentals-OneShot" -Confirm:$false
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName = "StockDashboard-Fundamentals-OneShot"
$BatchPath = "c:\Users\sk15y\claude\stock_dashboard\streamlit_app\scripts\update_fundamentals.bat"

if (-not (Test-Path $BatchPath)) {
    Write-Error "Batch file not found: $BatchPath"
    exit 1
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Removing existing one-shot task: $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute $BatchPath

# Trigger: exactly 65 minutes from NOW (registration time)
$startTime = (Get-Date).AddMinutes(65)
$trigger = New-ScheduledTaskTrigger -Once -At $startTime

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

# No-admin mode: Interactive logon + Limited run level. Task runs only
# while you're logged in (fine for a one-shot 65-min wait). If you need
# it to run when logged off, register the daily/weekly version from an
# admin PowerShell instead.
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "One-shot S&P 1500 fundamentals fetch (waits for yfinance cooldown)"

Write-Host ""
Write-Host "==> Registered ONE-SHOT: $TaskName" -ForegroundColor Green
Write-Host "    Will run at: $($startTime.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "    Batch:       $BatchPath"
Write-Host ""
Write-Host "Cancel before it runs:"
Write-Host "    Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
