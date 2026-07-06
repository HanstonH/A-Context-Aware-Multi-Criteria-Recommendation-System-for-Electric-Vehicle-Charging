param(
  [string]$TaskName = "EV-Live-Connector-Hourly",
  [string]$BatPath = ""
)

if (-not $BatPath) {
  $BatPath = Join-Path $PSScriptRoot "run_extract_live.bat"
}

if (-not (Test-Path $BatPath)) {
  throw "Batch file not found: $BatPath"
}

$action = New-ScheduledTaskAction -Execute $BatPath -WorkingDirectory (Split-Path $BatPath -Parent)

# Every 30 minutes at :05 and :35 past each hour.
$now = Get-Date
$hourStart = $now.Date.AddHours($now.Hour)
$at05 = $hourStart.AddMinutes(5)
$at35 = $hourStart.AddMinutes(35)
if ($now -lt $at05) {
  $start = $at05
} elseif ($now -lt $at35) {
  $start = $at35
} else {
  $start = $hourStart.AddHours(1).AddMinutes(5)
}

$trigger = New-ScheduledTaskTrigger -Once -At $start `
  -RepetitionInterval (New-TimeSpan -Minutes 30) `
  -RepetitionDuration (New-TimeSpan -Days 9999)

$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -MultipleInstances IgnoreNew `
  -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 5) `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
  -WakeToRun

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger $trigger `
  -Settings $settings `
  -Description "30-minute TDX live connector extraction (auto-restart on failure)" `
  -Force | Out-Null

Enable-ScheduledTask -TaskName $TaskName | Out-Null
Write-Output "Registered task: $TaskName (every 30 minutes)"
Write-Output "Batch: $BatPath"
Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object LastRunTime, LastTaskResult, NextRunTime | Format-List
