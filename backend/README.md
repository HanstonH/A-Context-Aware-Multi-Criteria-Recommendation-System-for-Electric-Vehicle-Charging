# MapExplore backend

Flask API that the Expo app (`app/`) calls for charger recommendations and the Gemini assistant.
Deployed on Railway: project `mapexplore-backend`, service `backend`.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | Status, station count, whether Gemini is configured |
| POST | `/api/recommend` | Ranked reachable chargers. Body: `lat`, `lng`, `battery_pct`, optional `city`, `limit`, `lang`, `capacity_kwh`, `wh_per_km` |
| POST | `/api/chat` | Gemini assistant with database tools. Body: the above plus `message`, `history` (`[{role, text}]`), `dest_id` |
| POST | `/api/explain` | Why one station got its rank (Gemini, or a rule-based text if Gemini fails). Body: the above plus `station_id` |
| GET | `/api/stations/<id>` | Station details, charging and parking rates |
| POST | `/api/voice` | Spoken question. Multipart: `audio` (m4a from the phone) and `data` (the `/api/chat` JSON without `message`). Returns `transcript`, `reply`, `stations`, and `speech` parts |
| GET | `/api/speech/<id>` | WAV audio for one `speech` part (ids expire after 10 minutes) |

## Voice (`voice.py`)

1. **Speech to text:** Gemini (`GEMINI_STT_MODELS`, default `gemini-3.5-flash-lite`) transcribes the recording, in Traditional Chinese or English.
2. **Answer:** the same assistant and tools as `/api/chat`, told that the answer will be spoken to a driver (1–3 short sentences, low thinking level). Voice tries the fastest model first (`GEMINI_VOICE_MODELS`, default `gemini-3.5-flash-lite`) and allows at most 3 tool rounds. While the speech is being transcribed, the server already ranks stations for the current battery and puts the top 3 in the prompt, so "where can I charge?" needs no tool round trip. The reply is in the language the driver spoke, whatever the app's language is (`lang` in the response).
3. **Text to speech:** the reply is split into a short first part and the rest, and both are synthesized in the background with `gemini-3.8-flash-tts` (voice `GEMINI_TTS_VOICE`, default Kore) through the Interactions API. The app plays part 1 while part 2 downloads. If a part fails, the app reads it with the phone's own voice.

Measured locally (2026-11-12, English question with the app in Chinese): the text answer arrives about 4.5 s after the recording is sent, and the first Gemini audio about 11 s after.

A model that answers 429 (out of free quota) is skipped for `GEMINI_COOLDOWN_S` (300 s), and a busy one (5xx) for 30 s, so requests don't wait on failures first. Speech requests don't use the SDK's automatic retries, and `/api/speech` gives up after `SPEECH_WAIT_S` (25 s), so the app switches to the phone's voice quickly when Gemini's voice is out of quota.

## How ranking works (`algorithm.py`)

Same approach as `AI/Algorithm/logic.py`:

1. **Range:** 0.85 × usable Wh ÷ Wh/km. The defaults are a 60 kWh pack at 180 Wh/km.
2. **Candidates:** the 25 nearest stations within range, capped at 40 km unless a city is given.
3. **Road distances:** one OSRM table call. If OSRM fails, straight line × 1.3.
4. **Score:** distance, wait and cost are each min-max normalized ("lower is better"), then combined as a weighted sum. The default weight is 1/3 each, and POI is not used.

Placeholders and data limits:
- **Waiting time:** `wait_model.py` gives every station the same value, so it doesn't change the ranking. To plug in Model A/B, replace `predict_wait_seconds` there; nothing else needs to change.
- **Prices:** only 270 of the 3,008 stations, almost all in Taipei, have a charging price. Stations without one get the median price of the other candidates.

## Gemini tools (`assistant.py`)

`find_stations`, `nearby_stations`, `recommend_stations` (runs the algorithm), `station_details`,
`battery_range`, `city_overview`. Models are tried in order from `GEMINI_MODELS`
(default `gemini-3.5-flash,gemini-2.5-flash,gemini-3.5-flash-lite`).

Free-tier limits seen on 2026-11-12: `gemini-3.5-flash` allows 20 requests a day and
`gemini-2.5-flash` 5 a minute. One answer with tools uses 2–3 requests, and a spoken
answer adds 1 transcription and 2 speech requests.

## Run locally

```bash
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt pytest   # Windows path
cp backend/.env.example backend/.env    # then fill in GEMINI_API_KEY
backend/.venv/Scripts/python -m backend  # http://localhost:8000 (Flask server; gunicorn is Linux-only)
backend/.venv/Scripts/python -m pytest backend/tests -q
```

To use it from the phone, set `EXPO_PUBLIC_API_URL=http://<PC LAN IP>:8000` in `app/.env`.

## Deploy (Railway)

From the repo root: `railway up --service backend --ci`.

- **What gets uploaded:** `.railwayignore` limits the upload to `backend/` and `database/ev_charging.db`.
- **Dockerfile path:** the service variable `RAILWAY_DOCKERFILE_PATH=backend/Dockerfile` points Railway at the Dockerfile.
- **Variables:** set them with `railway variable set NAME --stdin --service backend`. The options are listed in `.env.example`.
