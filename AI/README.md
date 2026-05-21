# EV Charging Station Recommendation

A final-project system for ranking EV charging stations using **distance**, **nearby points of interest (POI)**, and **predicted waiting time**. Scoring logic lives in `Algorithm/`; wait-time models are trained in the notebooks and served from `model/` and `model_B/`.

## Scoring goal

The target recommendation formula is a weighted sum (for now will change later):

```
total_score = distance × w1 + POI × w2 + waiting_time × w3
```

| Criterion | Meaning | Higher is better? |
|-----------|---------|-------------------|
| **Distance** | Road-network travel distance (meters) from the user to the station | No — shorter is better |
| **POI** | Aggregate score of nearby places (rating, reviews, proximity) | Yes |
| **Waiting time** | Predicted queue / session wait (seconds) | No — shorter is better |

Weights `w1`, `w2`, and `w3` are configurable. In `Algorithm/logic.py`, `Calculation_Model` currently uses four equal weights (`w_dist`, `w_poi`, `w_wait`, `w_eff`) with min–max normalization before summing; efficiency is an extra factor planned alongside the three above.

## Where things live

```
AI/
├── Algorithm/              # Scoring & Google APIs
│   ├── logic.py            # POI score, distance, total_score()
│   ├── get_Distance_EV.py  # Routes API (road distance)
│   ├── get_POI.py          # Places API (nearby POI)
│   └── app.py              # Streamlit dashboard (reads ranked CSV)
├── model/                  # Model A — station availability (classifiers + LSTM)
├── model_B/                # Model B — wait duration in seconds (regressors + LSTM)
├── ev_pathfinder/          # Inference orchestrator (Model A → Model B → routing)
├── data/                   # Station & training datasets
├── Time Series Forecast.ipynb           # Train availability models → `model/`
└── Time Series Forecast model B.ipynb   # Train duration models → `model_B/`
```

## Scoring implementation (`Algorithm/logic.py`)

`Calculation_Model` is the main entry point for station scores.

| Method | Role |
|--------|------|
| `get_distance_score()` / `process_distances()` | Driving distance via Google Routes API (not straight-line) |
| `get_POI()` / `POI_score()` / `process_all_stations()` | Nearby POI from Google Places API; per-place score from rating, review count, and distance |
| `total_score()` | Normalizes distance, POI, waiting time (and efficiency), applies weights, sorts stations |

**POI score** (per place, then summed):

```text
poi_score = (rating × log10(reviews + 1)) / (1 + distance_meters / 100)
```

**Distance** uses `get_Distance_EV.get_distance_ev(destination, user_location)` and reads `routes[0].distanceMeters`.

**Waiting time** in `logic.py` is still a placeholder (`numpy.random` minutes in `main()`). The intended production path is the two-stage ML pipeline below.

Run the batch pipeline and write results:

```bash
cd Algorithm
python logic.py
```

Output: `final_recommendations_summary.csv` (used by `Algorithm/app.py`).

## Waiting time — two-stage ML

Waiting time is one scoring criterion. Prediction is split into two models:

1. **Model A** (`model_A/`) — Will the station be **available** when the user arrives?  
   - Binary classification: available vs occupied  
   - Artifacts: XGBoost, Random Forest, Decision Tree, Logistic Regression, LSTM (`lstm.pkl` / Keras)

2. **Model B** (`model_B/`) — If occupied, **how long** until it is free?  
   - Regression on session duration  
   - Output: **seconds** (also exposed as minutes in `ev_pathfinder`)  
   - Artifacts: same classifier families plus `lstm_duration.keras`

Training and experimentation:

- `Time Series Forecast.ipynb` → availability → `model/`
- `Time Series Forecast model B.ipynb` → duration → `model_B/`

At inference, `ev_pathfinder/` loads both folders, runs Model A, and only runs Model B when the station is predicted occupied. It also combines **travel time** (Google Routes) with **wait time** for pathfinding (`T_total = T_travel + T_wait`).

```bash
python -m ev_pathfinder
```

## Environment

Create a `.env` in the project root (see `.gitignore`):

```env
GOOGLE_MAPS_API_KEY=your_key_here
```

Required for distance and POI calls in `Algorithm/`, and for routing in `ev_pathfinder/`.

Python dependencies are expected in a local virtual environment (`.venv/`). Install packages used by your notebooks and scripts (e.g. `pandas`, `numpy`, `requests`, `python-dotenv`, `scikit-learn`, `tensorflow`, `streamlit`, `folium`).

## Data

| File | Use |
|------|-----|
| `data/ev_stations_2025.csv` | Sample stations for `logic.py` `main()` |
| `data/ChargePointData2011-2020-ManullyPreCleaned3.csv` | Raw sessions for model training |
| `data/Final_Cleaned_Dataset.csv` | Cleaned training data |
| `preprocessor_pipeline.joblib` | Feature pipeline for `ev_pathfinder` inference |

## Roadmap (from `logic.py` comments)

- [x] Road-following distance (Google Routes)
- [x] POI scoring
- [ ] Plug **Model A + Model B** into `Calculation_Model` instead of random wait times
- [ ] Align `total_score()` with `distance × w1 + POI × w2 + waiting_time × w3` only (optional: keep efficiency as `w4`)
- [ ] Change efficiency to battery usage by SUMO simulation dataset

## License & context

University final project — EV station recommendation for Taiwan / international datasets as configured in your CSVs and APIs.
