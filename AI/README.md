# AI — EV Charging Station Recommendation (Taiwan)

University final-project code for **ranking and explaining EV charging stations** in Taiwan. The active pipeline uses **TDX** (Transport Data eXchange) for station metadata, live availability, and pricing, plus **Google Maps** for road distance and nearby points of interest. Optional **Gemini** explanations are generated after ranking.

---

## Quick reference

| Item | Value |
|------|--------|
| **Domain** | EV charging station recommendation |
| **Geography** | Taiwan (city-scoped via TDX, e.g. `Taipei`) |
| **Primary goal** | Given user location + battery %, find reachable stations with free connectors, score them, pick the best |
| **Ranking** | Weighted sum of normalized distance, POI, cost, availability (0.25 each for now) |
| **Main entry point** | `python logic.py` from `Algorithm/` |
| **Secrets** | `AI/.env` (gitignored) |

---

## How it works

```mermaid
flowchart LR
    U[User lat/lon + battery %] --> TDX[TDX API]
    TDX --> Filter[Reachable + available now]
    Filter --> Top10[10 closest candidates]
    Top10 --> GMaps[Google Routes + Places]
    GMaps --> Score[Weighted total_score]
    Score --> Best[Best station]
    Score -. optional .-> LLM[Gemini explanation]
>>>>>>> taiwan
```

1. **Battery range** — remaining drive distance is estimated from battery %, full range (default 300 km), and a safety factor (default 0.8).
2. **TDX fetch** — stations, live connector status, and charging rates for the chosen city.
3. **Filter** — keep stations within range that have at least one connector available now (`ConnectorStatus == 1`).
4. **Shortlist** — take the 10 closest by straight-line distance (limits paid Google API calls).
5. **Enrich** — road distance (Routes API), POI score (Places API New), cost (TDX rates).
6. **Rank** — `total_score` picks the winner. Equal weights today; tunable later.

---

## Project layout

```
AI/
├── README.md                 ← you are here
├── .env                      ← API keys (gitignored; see Environment)
├── .venv/                    ← Python virtual environment
│
├── Algorithm/                ← active Taiwan recommender
│   ├── logic.py              ← Calculation_Model + recommend() pipeline
│   ├── API.py                ← TDX OAuth client (stations, live status, rates)
│   ├── get_Distance_EV.py    ← Google Routes API (road distance)
│   ├── get_POI.py            ← Google Places API (New) — nearby POI
│   ├── get_cache.py          ← POI response cache helper
│   ├── llm.py                ← Gemini draft → critique → final explanation
│   └── final_recommendations_summary.csv   ← output from logic.py main()
│
└── archive/                  ← legacy US / Palo Alto code (reference only)
    ├── README.md
    └── legacy_us/            ← old models, notebooks, ev_pathfinder, ChargePoint data
```

**Do not use `archive/` for new development** unless you explicitly need the old Palo Alto stack. Consider adding `AI/archive/**` to `.cursorignore` to keep AI agents from loading legacy context.

---

## Setup

### 1. Virtual environment

```powershell
cd AI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pandas numpy requests python-dotenv google-genai
```

(Install any other packages as needed when imports fail.)

### 2. Environment variables

Create `AI/.env`:

```env
GOOGLE_MAPS_API_KEY=your_google_maps_key
GEMINI_API_KEY=your_gemini_key          # optional; only for llm.py
TDX_CLIENT_ID=your_tdx_client_id
TDX_CLIENT_SECRET=your_tdx_client_secret
```

| Key | Used by | Purpose |
|-----|---------|---------|
| `GOOGLE_MAPS_API_KEY` | `get_Distance_EV.py`, `get_POI.py` | Routes API + Places API (New) |
| `GEMINI_API_KEY` | `llm.py` | Natural-language recommendation explanation |
| `TDX_CLIENT_ID` / `TDX_CLIENT_SECRET` | `API.py`, `logic.py` | TDX OAuth2 client credentials |

**TDX:** register at [tdx.transportdata.tw](https://tdx.transportdata.tw) and create API keys in the member center.  
**Google:** enable **Routes API** and **Places API (New)** for the same key.

---

## Running

### Full recommendation pipeline

```powershell
cd AI\Algorithm
python logic.py
```

This runs the Taipei demo (user near Taipei Main Station, 35% battery), writes `final_recommendations_summary.csv`, prints ranked stations, and attempts an LLM reflection if `GEMINI_API_KEY` is set.

### Programmatic use

```python
from logic import Calculation_Model

user_location = (25.0478, 121.5170)   # (lat, lon)
battery_percent = 35.0

model = Calculation_Model(user_location, battery_percent, city="Taipei")
ranked = model.recommend(include_llm_context=True)

best = ranked.iloc[0]
print(best["station_name"], best["total_score"])
```

### Test TDX only

```powershell
cd AI\Algorithm
python API.py
```

### Test distance / POI helpers

```powershell
python get_Distance_EV.py
python get_POI.py
>>>>>>> taiwan
```

---

## Scoring (`Algorithm/logic.py`)

### Criteria

| Criterion | Column | Source | Better direction |
|-----------|--------|--------|------------------|
| Distance | `distance` | Google Routes API (metres) | Lower |
| POI | `poi_sum` | Google Places + local score | Higher |
| Cost | `cost` | TDX `ChargingRate` (median per station) | Lower |
| Availability | `available_points` | TDX `ConnectorLiveStatus` (idle count) | Higher |

Default weights on `Calculation_Model`: `w_dist`, `w_poi`, `w_cost`, `w_avail` = **0.25** each.

`total_score()` min–max normalizes each factor within the candidate set, applies weights, and sorts **descending** by `total_score`.

### POI score (per place, then summed)

```text
poi_score = (rating × log10(reviews + 1)) / (1 + distance_meters / 100)
```

### TDX city codes

Pass English enum values to `city=`, e.g. `Taipei`, `NewTaipei`, `Taichung`, `Kaohsiung`. Full list is in `API.TDX_CITIES`.

---

## External APIs

### TDX (`API.py`)

| Endpoint | Purpose |
|----------|---------|
| `/v1/EV/Station/City/{City}` | Station name, lat/lon, spaces |
| `/v1/EV/ConnectorLiveStatus/City/{City}` | Live connector availability |
| `/v1/EV/ChargingRate/City/{City}` | Charging prices |
| `/v1/EV/ParkingRate/City/{City}` | Parking prices (wrapped; not yet in scoring) |

Auth: OAuth2 client credentials → Bearer token (auto-refreshed in `TDXClient`).

### Google Maps

| Module | API | Notes |
|--------|-----|-------|
| `get_Distance_EV.py` | Routes API `computeRoutes` | `DRIVE`, traffic-aware; very short trips may omit `distanceMeters` (fallback to straight-line in `logic.py`) |
| `get_POI.py` | Places API (New) `places:searchNearby` | Coffee shops, restaurants, malls, parks within 500 m |

---

## LLM explanations (`llm.py`)

After ranking with `include_llm_context=True`, each row gets an `llm_context` dict. Feed the top pick plus alternatives into:

```python
from llm import run_reflection_pipeline, print_reflection_report

reflection = run_reflection_pipeline({
    "recommended": ranked.iloc[0]["llm_context"],
    "alternatives": ranked.iloc[1:4]["llm_context"].tolist(),
})
print_reflection_report(reflection)
```

Requires `GEMINI_API_KEY`. Ranking works without it.

---

## Archive (`archive/legacy_us/`)

Previous iteration targeted **Palo Alto, CA** with:

- ChargePoint session CSVs and unit-price tables  
- Model A / Model B wait-time prediction (availability + duration)  
- `ev_pathfinder` Flask web UI  
- US holiday / weather feature engineering  

That code is kept for reference and comparison. The Taiwan pipeline replaces wait-time ML with **live TDX connector counts** and replaces static US price CSVs with **TDX charging rates**.

---

## Known limitations

- **Cost comparison** — TDX rates can be per-kWh, per-minute, or free; scoring uses a simplified median per station.
- **Battery model** — linear `% × range` estimate; not tied to a specific vehicle yet.
- **API quota** — full `recommend()` calls TDX once per run plus ~20 Google calls (10 routes + 10 POI searches).
- **Routes edge case** — degenerate ~0 s routes may lack `distanceMeters`; straight-line fallback is used.

---

## License / attribution

TDX data is provided by Taiwan MOTC under their platform terms. Google Maps and Gemini usage are subject to Google API terms. See course/university requirements for project licensing.
