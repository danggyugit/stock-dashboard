# =====================================================================
#  SEC Intelligence Task Scheduler 등록 스크립트
#
#  실행 (관리자 PowerShell):
#     powershell -ExecutionPolicy Bypass -File register_sec_intelligence.ps1
#
#  제거:
#     Unregister-ScheduledTask -TaskName "StockDashboard-SecIntelligence" -Confirm:$false
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName  = "StockDashboard-SecIntelligence"
$BatchPath = "c:\Users\sk15y\claude\stock_dashboard\streamlit_app\scripts\run_sec_intelligence.bat"

if (-not (Test-Path $BatchPath)) {
    Write-Error "Batch file not found: $BatchPath"
    exit 1
}

# 기존 태스크 제거
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Removing existing task: $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Action: bat 파일 실행
$action = New-ScheduledTaskAction -Execute $BatchPath

# Trigger: 매일 11:30 KST
$trigger = New-ScheduledTaskTrigger -Daily -At "11:30"

# Settings
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

# Principal: 현재 사용자, 로그인 없이 실행
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Description "Daily SEC EDGAR 내부자 스캔 + 분기 13F 고래 포트폴리오 수집 + Telegram 알림"

Write-Host ""
Write-Host "==> 등록 완료: $TaskName" -ForegroundColor Green
Write-Host "    실행 시간: 매일 11:30 KST"
Write-Host "    Batch:    $BatchPath"
Write-Host ""
Write-Host "지금 바로 실행하려면:"
Write-Host "    Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "Task Scheduler에서 확인: taskschd.msc"
