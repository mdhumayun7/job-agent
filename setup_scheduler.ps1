$taskName = "JobAgentPro"
$batFile = (Resolve-Path "run_daily.bat").Path
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$batFile`" >> logs\scheduler.log 2>&1"
$trigger = New-ScheduledTaskTrigger -Daily -At "08:00AM"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest

try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Task Scheduler Setup COMPLETE!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Task Name : JobAgentPro" -ForegroundColor White
    Write-Host "  Runs At   : 8:00 AM Daily" -ForegroundColor White
    Write-Host "  Log File  : logs\scheduler.log" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To change time: Task Scheduler > JobAgentPro > Properties" -ForegroundColor Yellow
    Write-Host "To run now: Start-ScheduledTask -TaskName JobAgentPro" -ForegroundColor Yellow
    Write-Host "To remove: Unregister-ScheduledTask -TaskName JobAgentPro" -ForegroundColor Yellow
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Try running PowerShell as Administrator" -ForegroundColor Yellow
}
