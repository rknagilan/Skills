# Makes AutoClip start automatically when you log in to Windows. Run once with PowerShell.
$bat = Join-Path $PSScriptRoot "start-autoclip.bat"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "AutoClip" -Action $action -Trigger $trigger -Settings $settings -Force
powercfg /change standby-timeout-ac 0
Write-Host "AutoClip will start at every login. Sleep is turned off while plugged in." -ForegroundColor Green
