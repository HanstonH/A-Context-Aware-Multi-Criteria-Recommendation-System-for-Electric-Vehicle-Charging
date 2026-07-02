# Extraction automation (Synology-backed)

This project now includes an extraction package under `AI/extraction` that archives full TDX JSON and builds processed files.

## Data root

Default root (already configured for your Synology Drive):

`C:\Users\hanst\SynologyDrive\ev-data`

Override temporarily:

```powershell
python -m extraction --data-root "D:\some\other\path" status
```

## Commands

From `D:\University\Final_Project\Coding\AI`:

```powershell
python -m extraction init
python -m extraction static
python -m extraction live
python -m extraction status
```

## Output format

### Static raw JSON

- `static/raw/stations/<City>/<YYYY-MM-DD>.json`
- `static/raw/charging_rates/<City>/<YYYY-MM-DD>.json`
- `static/raw/parking_rates/<City>/<YYYY-MM-DD>.json`

### Live raw JSON (hourly)

- `live/raw/<YYYY-MM-DD>/hour-<HH>/<City>.json`

### Processed outputs

- `static/processed/stations_master.parquet`
- `live/processed/latest.parquet`
- `live/processed/daily/<YYYY-MM-DD>.parquet`

### Progress tracking

- `manifest.db` (SQLite task/run log)
- `state/checkpoint.json` (human-readable summary)
- `logs/extraction_<YYYY-MM-DD>.log`

## Scheduling (Windows Task Scheduler)

You can register the hourly live job automatically:

```powershell
powershell -ExecutionPolicy Bypass -File "D:\University\Final_Project\Coding\AI\scripts\register_live_task.ps1"
```

This creates a task that runs every hour from 00:05 using:

`D:\University\Final_Project\Coding\AI\scripts\run_extract_live.bat`

If you want to do it manually in Task Scheduler:

- Program/script: `D:\University\Final_Project\Coding\AI\scripts\run_extract_live.bat`
- Trigger: Daily, repeat every 1 hour, indefinitely
- Start time: 00:05
- Option: Run task as soon as possible after a scheduled start is missed

## Notes

- Full static extraction stores complete TDX JSON payloads.
- `LienchiangCounty` is currently skipped for EV endpoints because TDX returns HTTP 400.
- No raw folders are auto-deleted.
