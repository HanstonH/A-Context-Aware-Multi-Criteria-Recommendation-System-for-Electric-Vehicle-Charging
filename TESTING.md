# Testing Guide

This project has three layers, and each one has its own automated test suite:

```
frontend (Next.js)  ──►  ev-charging-backend (Express)  ──►  AI/Algorithm (FastAPI + TOPSIS)
   vitest                     node:test + supertest               pytest
```

All automated tests run **offline**. TDX, Google Routes/Places and FastAPI
are replaced with fakes, so you need **no API keys** and the tests use no paid quota.
GitHub Actions runs all three suites on every push and pull request (`.github/workflows/tests.yml`).

| Layer | Folder | Command | What it covers |
|-------|--------|---------|----------------|
| AI recommender | `AI/` | `pytest` | weight engine, TOPSIS, full `Calculation_Model` pipeline, FastAPI endpoints |
| Backend API | `ev-charging-backend/` | `npm test` | every `/api/*` route, input validation, error mapping (400/502/503/500), register/login |
| Frontend logic | `frontend/` | `pnpm test` | TS TOPSIS + weights, client-side ranking, API response normalisation |

---

## 1. AI recommender (Python / pytest)

```bash
cd AI
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r Algorithm/requirements.txt -r requirements-dev.txt
pytest
```

Useful variants:

```bash
pytest tests/test_topsis.py          # one file
pytest -k urgent                     # tests whose name contains "urgent"
pytest -x -vv                        # stop at first failure, verbose
```

### Test files

| File | Kind | What is tested |
|------|------|----------------|
| `tests/test_weights.py` | unit | weights always sum to 1; low battery → distance/availability, high battery → cost; urgency override; clamping; state labels at 20 % / 50 % boundaries |
| `tests/test_topsis.py` | unit | dominant station scores 1.0; scores in [0, 1] and sorted; identical stations → 0.5; battery level flips the winner; urgent users never get a full station first; inputs are not mutated |
| `tests/test_helpers.py` | unit | haversine distance, Google polyline decoding (official example), POI parsing, rate → cost collapsing, normalisation |
| `tests/test_calculation_model.py` | integration | TDX merge (availability + cost), candidate filtering (range, availability, fallback, max candidates), Routes API failure handling, full `recommend()` with live-style and snapshot data |
| `tests/test_api.py` | API | `/health`, `/recommend`, `/stations/{city}`, `/pois`, `/route`: happy paths, 400/404/422/500/502 |
| `tests/test_live_smoke.py` | live | real TDX + Google calls. **Skipped by default** |

### How the mocking works (`tests/conftest.py`)

* `FakeTDXClient` returns 4 small hand-made stations near Taipei 101 (one cheap, one full, one mid-distance, one in Taichung that is out of range at low battery). You pass it in as `tdx_client=`.
* The `fake_google` fixture replaces `get_distance_ev` (road distance = straight line × 1.3) and `Get_POI` (one coffee shop per station).
* Any real HTTP request through `requests` raises an error, so a forgotten mock can't spend your Google credit.

### Live smoke tests (before a demo)

Put real keys in `AI/.env` (`TDX_CLIENT_ID`, `TDX_CLIENT_SECRET`, `GOOGLE_MAPS_API_KEY`), then run:

```bash
RUN_LIVE_TESTS=1 pytest -m live            # macOS/Linux
set RUN_LIVE_TESTS=1 && pytest -m live      # Windows cmd
```

---

## 2. Express backend (Node / node:test + supertest)

```bash
cd ev-charging-backend
npm install
npm test
```

* `src/app.js` builds the Express app without starting a server. `index.js` only calls `listen()`, so supertest can call the routes directly.
* `test/helpers.js` creates a **throw-away SQLite DB** from `database/schema.sql` and points `DB_PATH` at it. Your real `database/ev_charging.db` is never touched.
* `axios` is stubbed in `test/proxy.test.js`, so **FastAPI does not need to be running**. The tests check that each route forwards the right URL and payload, and turns a FastAPI error into 502, "FastAPI is down" into 503 and any other failure into 500.
* `test/auth.test.js` checks registration, duplicate emails, bcrypt hashing, login success, wrong password (401) and unknown user (404).

---

## 3. Frontend (Next.js / vitest)

```bash
cd frontend
pnpm install
pnpm test          # run once
pnpm test:watch    # re-run on save while developing
```

Tests live in `frontend/tests/` and cover the pure logic in `lib/`:

* `lib/ai/weights.ts` and `lib/ai/topsis.ts`, the TypeScript port of the Python algorithm
* `lib/ai/recommend-stations.ts`: range filter, availability filter, ranking, reason text
* `lib/api/normalize.ts`: mapping the FastAPI `/recommend` JSON to `RecommendItem`

---

## 4. Manual end-to-end test (whole system)

Run this before a presentation, after the automated suites pass.

1. **FastAPI** (needs `AI/.env`):
   ```bash
   cd AI/Algorithm && uvicorn app:app --port 8000
   ```
   Open <http://localhost:8000/docs>. Swagger UI lets you try `/recommend` from the browser.
2. **Backend**:
   ```bash
   cd ev-charging-backend && npm start          # http://localhost:5000
   ```
   ```bash
   curl -X POST http://localhost:5000/api/recommend -H "Content-Type: application/json" \
        -d '{"lat":25.0330,"lng":121.5654,"battery_percent":15}'
   ```
3. **Frontend**:
   ```bash
   cd frontend && pnpm dev                      # http://localhost:3000
   ```

### Scenario checklist

| # | Scenario | Input | Expected |
|---|----------|-------|----------|
| 1 | Low battery | Taipei 101, battery 10 % | Closest stations with free connectors on top; nothing beyond ~24 km |
| 2 | High battery | Taipei 101, battery 90 % | Cheaper stations rise in the ranking |
| 3 | Urgent | battery 50 %, `is_available_now: true` | No station with 0 free connectors ranked first |
| 4 | Empty battery | battery 0 % | Clear error ("No station reachable"), no crash |
| 5 | Invalid city | `city: "Tokyo"` | HTTP 400 |
| 6 | FastAPI stopped | stop uvicorn, call backend | HTTP 503 "Is the FastAPI server running?" |
| 7 | Route drawing | pick a station in the UI | Route polyline appears on the map |
| 8 | Register / login | new email, then wrong password | 201, then 401 |

---

## Writing a new test

* **Changed the algorithm?** Add a case to `AI/tests/test_topsis.py` or `test_weights.py`. If you changed the same logic in `frontend/lib/ai`, add the matching case to `frontend/tests/`, so the Python and TypeScript versions stay in agreement.
* **New FastAPI endpoint?** Add it to `AI/tests/test_api.py`. Patch any Google/TDX call with `monkeypatch.setattr(app_module, "...", fake)`.
* **New Express route?** Add a `describe` block to `ev-charging-backend/test/proxy.test.js` and stub axios with `mock.method(axios, 'get' | 'post', ...)`.
