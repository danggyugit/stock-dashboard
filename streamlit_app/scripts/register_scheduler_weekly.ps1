# =====================================================================
#  Register a TWICE-WEEKLY scheduled task that refreshes
#  fundamentals.json with the full S&P 1500 universe.
#  Runs every Monday and Friday at 03:00.
#
#  Run this once from an elevated PowerShell window (Run as Admin):
#     powershell -ExecutionPolicy Bypass -File register_scheduler_weekly.ps1
#
#  To remove later:
#     Unregister-ScheduledTask -TaskName "StockDashboard-Fundamentals" -Confirm:$false
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName = "StockDashboard-Fundamentals"
$BatchPath = "c:\Users\sk15y\claude\stock_dashboard\streamlit_app\scripts\update_fundamentals.bat"

if (-not (Test-Path $BatchPath)) {
    Write-Error "Batch file not found: $BatchPath"
    exit 1
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Removing existing task: $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute $BatchPath

# Trigger: every Monday + Friday at 03:00 local time
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday, Friday `
    -At "03:00"

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Twice-weekly (Mon/Fri) S&P 1500 fundamentals refresh + git push"

Write-Host ""
Write-Host "==> Registered: $TaskName" -ForegroundColor Green
Write-Host "    Schedule: every Monday and Friday at 03:00"
Write-Host "    Batch:    $BatchPath"
Write-Host ""
Write-Host "View it in: taskschd.msc -> Task Scheduler Library"
Write-Host "Run it now: Start-ScheduledTask -TaskName $TaskName"
