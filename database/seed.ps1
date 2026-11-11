# Build database/ev_charging.db (SQLite, no Supabase).
# Uses git show to pull TDX snapshots from origin/main.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DbDir = $PSScriptRoot
$DbPath = Join-Path $DbDir "ev_charging.db"
$SchemaPath = Join-Path $DbDir "schema.sql"
$SqliteDir = Join-Path $DbDir "_tmp"
$SqliteExe = Join-Path $SqliteDir "sqlite3.exe"

function Get-Sqlite3 {
    if (Get-Command sqlite3 -ErrorAction SilentlyContinue) {
        return (Get-Command sqlite3).Source
    }
    $existing = Get-ChildItem -Path $SqliteDir -Filter sqlite3.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) {
        return $existing.FullName
    }
    New-Item -ItemType Directory -Force -Path $SqliteDir | Out-Null
    $zip = Join-Path $SqliteDir "sqlite-tools.zip"
    $url = "https://www.sqlite.org/2025/sqlite-tools-win-x64-3500400.zip"
    Write-Host "Downloading SQLite tools..."
    Invoke-WebRequest -Uri $url -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $SqliteDir -Force
    $found = Get-ChildItem -Path $SqliteDir -Filter sqlite3.exe -Recurse | Select-Object -First 1
    if (-not $found) {
        throw "sqlite3.exe not found after download"
    }
    return $found.FullName
}

function Write-Utf8([string]$path, [string]$text) {
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($path, $text, $utf8)
}

function Sql-Literal($value) {
    if ($null -eq $value -or $value -eq "") { return "NULL" }
    return "'" + ([string]$value -replace "'", "''") + "'"
}

function Sql-Num($value) {
    if ($null -eq $value -or $value -eq "") { return "NULL" }
    return ([string]$value)
}

function Git-ShowJson([string]$spec) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "git"
    $psi.Arguments = "show `"$spec`""
    $psi.WorkingDirectory = $Root
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
    $proc = [Diagnostics.Process]::Start($psi)
    $text = $proc.StandardOutput.ReadToEnd()
    $err = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    if ($proc.ExitCode -ne 0) {
        throw "git show failed: $spec`n$err"
    }
    return $text | ConvertFrom-Json
}

function Read-SqlFile([string]$sqlite, [string]$path) {
    $posix = ($path -replace '\\', '/')
    & $sqlite $DbPath ".read $posix"
}

function Flush-Sql([string]$sqlite, [System.Collections.Generic.List[string]]$lines) {
    if ($lines.Count -eq 0) { return }
    $sqlOut = Join-Path $SqliteDir "seed.sql"
    Write-Utf8 $sqlOut ($lines -join "`n")
    Read-SqlFile $sqlite $sqlOut
    $lines.Clear()
}

$TdxCities = @(
    "Taipei", "NewTaipei", "Taoyuan", "Taichung", "Tainan", "Kaohsiung",
    "Keelung", "Hsinchu", "HsinchuCounty", "MiaoliCounty", "ChanghuaCounty",
    "NantouCounty", "YunlinCounty", "ChiayiCounty", "Chiayi", "PingtungCounty",
    "YilanCounty", "HualienCounty", "TaitungCounty", "KinmenCounty",
    "PenghuCounty"
)
$SnapshotDate = "2026-07-02"

$sqlite = Get-Sqlite3
New-Item -ItemType Directory -Force -Path $SqliteDir | Out-Null
if (Test-Path $DbPath) { Remove-Item $DbPath }

$copiedSchema = Join-Path $SqliteDir "schema.sql"
Copy-Item $SchemaPath $copiedSchema -Force
Read-SqlFile $sqlite $copiedSchema

# Demo user: sha256$ev-local-v1$...
$password = "demo123"
$salt = "ev-local-v1"
$sha = [System.Security.Cryptography.SHA256]::Create()
$hashBytes = $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes("${salt}:${password}"))
$hash = -join ($hashBytes | ForEach-Object { $_.ToString("x2") })
$passwordHash = "sha256`$$salt`$$hash"

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("PRAGMA foreign_keys = ON;")
$lines.Add("INSERT INTO users (email, password_hash, name, phone) VALUES ('demo@ev.local', $(Sql-Literal $passwordHash), 'Demo Driver', '0900000000');")
$lines.Add("INSERT INTO user_vehicles (user_id, label, capacity_kwh, wh_per_km) VALUES (1, 'Default EV', 60, 180);")

$manifest = @{}
$manifestPath = Join-Path $Root "Simulation\charging_station_manifest.json"
if (Test-Path $manifestPath) {
    $manifest = Get-Content -Raw -Encoding UTF8 $manifestPath | ConvertFrom-Json
}

$prices = @{}
$pricePath = Join-Path $Root "AI\data\unit_price_by_station_taiwan.csv"
Import-Csv $pricePath | ForEach-Object { $prices[$_.'Station Name'] = $_ }

Import-Csv (Join-Path $Root "AI\data\taiwan_ev_stations.csv") | ForEach-Object {
    $id = $_.'MAC Address'
    $info = $manifest.$id
    $cs = if ($info) { $info.cs_id } else { $null }
    $lane = if ($info) { $info.lane } else { $null }
    $lines.Add(@"
INSERT INTO stations (station_id, source, name, address, operator, plug_type, latitude, longitude, city, sumo_cs_id, sumo_lane)
VALUES ($(Sql-Literal $id), 'project', $(Sql-Literal $_.'Station Name'), $(Sql-Literal $_.'Address 1'), $(Sql-Literal $_.'Address 1'), $(Sql-Literal $_.'Plug Type'), $(Sql-Num $_.Latitude), $(Sql-Num $_.Longitude), 'Taipei', $(Sql-Literal $cs), $(Sql-Literal $lane));
"@)
    $price = $prices[$_.'Station Name']
    if ($price) {
        $lines.Add("INSERT INTO station_prices (station_id, price_ntd_per_kwh, price_tier, source) VALUES ($(Sql-Literal $id), $(Sql-Num $price.median_unit_price_per_kwh), $(Sql-Num $price.price_tier), 'project');")
    }
}
Flush-Sql $sqlite $lines

foreach ($city in $TdxCities) {
    Write-Host "Loading TDX stations $city..."
    try {
        $body = Git-ShowJson "origin/main:static/raw/stations/$city/$SnapshotDate.json"
    } catch {
        Write-Host "  skip stations $city"
        continue
    }
    foreach ($s in @($body.Stations)) {
        if (-not $s.StationID -or $null -eq $s.PositionLat -or $null -eq $s.PositionLon) { continue }
        $name = $null
        if ($s.StationName) { $name = $s.StationName.Zh_tw }
        $lines.Add(@"
INSERT OR IGNORE INTO stations (station_id, source, name, latitude, longitude, city, spaces, charging_points)
VALUES ($(Sql-Literal $s.StationID), 'tdx', $(Sql-Literal $name), $(Sql-Num $s.PositionLat), $(Sql-Num $s.PositionLon), $(Sql-Literal $city), $(Sql-Num $s.Spaces), $(Sql-Num $s.ChargingPoints));
"@)
    }
    Flush-Sql $sqlite $lines
}

$parkingByStation = @{}
foreach ($city in $TdxCities) {
    Write-Host "Loading TDX parking rates $city..."
    try {
        $body = Git-ShowJson "origin/main:static/raw/parking_rates/$city/$SnapshotDate.json"
    } catch {
        Write-Host "  skip parking $city"
        continue
    }
    $fetched = $body.UpdateTime
    foreach ($rec in @($body.ParkingRates)) {
        foreach ($rate in @($rec.Rates)) {
            $lines.Add(@"
INSERT INTO parking_rates (station_id, city, rate_type, pricing_type, day_type, rate_price, max_price, fetched_at)
VALUES ($(Sql-Literal $rec.StationID), $(Sql-Literal $city), $(Sql-Num $rate.RateType), $(Sql-Num $rate.PricingType), $(Sql-Num $rate.DayType), $(Sql-Num $rate.RatePrice), $(Sql-Num $rate.MaxPrice), $(Sql-Literal $fetched));
"@)
            if ($rec.StationID -and $null -ne $rate.RatePrice) {
                if (-not $parkingByStation.ContainsKey($rec.StationID)) {
                    $parkingByStation[$rec.StationID] = New-Object System.Collections.Generic.List[double]
                }
                $parkingByStation[$rec.StationID].Add([double]$rate.RatePrice)
            }
        }
    }
    Flush-Sql $sqlite $lines
}

foreach ($sid in $parkingByStation.Keys) {
    $sorted = @($parkingByStation[$sid] | Sort-Object)
    if ($sorted.Count -eq 0) { continue }
    $mid = [int][Math]::Floor($sorted.Count / 2)
    $median = if ($sorted.Count % 2 -eq 1) { $sorted[$mid] } else { ($sorted[$mid - 1] + $sorted[$mid]) / 2 }
    $lines.Add("UPDATE station_prices SET parking_cost = $(Sql-Num $median) WHERE station_id = $(Sql-Literal $sid) AND source = 'tdx';")
    $lines.Add("INSERT OR IGNORE INTO station_prices (station_id, parking_cost, source) SELECT $(Sql-Literal $sid), $(Sql-Num $median), 'tdx' WHERE EXISTS (SELECT 1 FROM stations WHERE station_id = $(Sql-Literal $sid));")
}
Flush-Sql $sqlite $lines

Write-Host "Loading TDX Taipei charging rates..."
$rates = Git-ShowJson "origin/main:static/raw/charging_rates/Taipei/2026-07-02.json"
$fetched = $rates.UpdateTime
$rateByStation = @{}
foreach ($rec in @($rates.ChargingRates)) {
    foreach ($rate in @($rec.Rates)) {
        $lines.Add(@"
INSERT INTO charging_rates (station_id, charging_point_id, connector_id, city, rate_type, pricing_type, rate_price, peak, start_time, end_time, fetched_at)
VALUES ($(Sql-Literal $rec.StationID), $(Sql-Literal $rec.ChargingPointID), $(Sql-Literal $rec.ConnectorID), 'Taipei', $(Sql-Num $rate.RateType), $(Sql-Num $rate.PricingType), $(Sql-Num $rate.RatePrice), $(Sql-Num $rate.Peak), $(Sql-Literal $rate.StartTime), $(Sql-Literal $rate.EndTime), $(Sql-Literal $fetched));
"@)
        if ($rec.StationID -and $null -ne $rate.RatePrice) {
            if (-not $rateByStation.ContainsKey($rec.StationID)) {
                $rateByStation[$rec.StationID] = New-Object System.Collections.Generic.List[object]
            }
            $rateByStation[$rec.StationID].Add(@{ Type = $rate.RateType; Price = [double]$rate.RatePrice })
        }
    }
}

foreach ($sid in $rateByStation.Keys) {
    $items = $rateByStation[$sid]
    $preferred = @($items | Where-Object { $_.Type -eq 2 } | ForEach-Object { $_.Price })
    $vals = if ($preferred.Count -gt 0) { $preferred } else { @($items | ForEach-Object { $_.Price }) }
    $sorted = $vals | Sort-Object
    $mid = [int][Math]::Floor($sorted.Count / 2)
    $median = if ($sorted.Count % 2 -eq 1) { $sorted[$mid] } else { ($sorted[$mid - 1] + $sorted[$mid]) / 2 }
    $lines.Add("INSERT OR IGNORE INTO station_prices (station_id, price_ntd_per_kwh, source) SELECT $(Sql-Literal $sid), $(Sql-Num $median), 'tdx' WHERE EXISTS (SELECT 1 FROM stations WHERE station_id = $(Sql-Literal $sid));")
}

$lines.Add("INSERT INTO recommendation_requests (user_id, latitude, longitude, battery_pct, city) VALUES (1, 25.0330, 121.5654, 45, 'Taipei');")
Import-Csv (Join-Path $Root "AI\Algorithm\final_recommendations_summary.csv") | ForEach-Object {
    $lines.Add(@"
INSERT INTO recommendation_results (request_id, station_id, station_name, latitude, longitude, distance_m, waiting_time, poi_sum, cost, total_score, rank, explanation)
VALUES (1, $(Sql-Literal $_.'MAC Address'), $(Sql-Literal $_.'Station Name'), $(Sql-Num $_.lat), $(Sql-Num $_.lon), $(Sql-Num $_.distance), $(Sql-Num $_.waiting_time), $(Sql-Num $_.poi_sum), $(Sql-Num $_.cost), $(Sql-Num $_.total_score), $(Sql-Num $_.rank), $(Sql-Literal $_.score_explanation));
"@)
}

$sqlOut = Join-Path $SqliteDir "seed.sql"
Write-Utf8 $sqlOut ($lines -join "`n")
Write-Host "Applying remaining seed SQL ($($lines.Count) statements)..."
Flush-Sql $sqlite $lines

Write-Host ""
Write-Host "Created $DbPath"
@("users", "user_vehicles", "stations", "station_prices", "charging_rates", "parking_rates", "recommendation_requests", "recommendation_results") | ForEach-Object {
    $n = & $sqlite $DbPath "SELECT COUNT(*) FROM $_;"
    Write-Host ("  {0}: {1}" -f $_, $n)
}
Write-Host "Demo login: demo@ev.local / demo123"
