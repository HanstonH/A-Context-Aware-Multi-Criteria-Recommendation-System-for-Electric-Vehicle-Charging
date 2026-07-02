param(
  [string]$TaskName = "EV-Live-Connector-Hourly",
  [string]$BatPath = "D:\University\Final_Project\Coding\AI\scripts\run_extract_live.bat"
)

if (-not (Test-Path $BatPath)) {
  throw "Batch file not found: $BatPath"
}

$action = New-ScheduledTaskAction -Execute $BatPath
$start = (Get-Date).Date.AddMinutes(5)
$trigger = New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Hourly TDX live connector extraction" -Force
Write-Output "Registered task: $TaskName"
