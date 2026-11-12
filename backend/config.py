"""Settings, read from environment variables (Railway "Variables", or backend/.env locally)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
REPO_DIR = BACKEND_DIR.parent

# Local development only: Railway injects variables directly.
load_dotenv(BACKEND_DIR / ".env")


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


DB_PATH = Path(os.getenv("DB_PATH", REPO_DIR / "database" / "ev_charging.db"))

# ── Gemini ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Tried in order; the next one is used when a model is busy (503) or out of quota (429).
# Free tier (checked 2026-11-12): gemini-3.5-flash allows only 20 requests/day and
# gemini-2.5-flash 5/minute, and one tool-using answer takes 2-3 requests.
GEMINI_MODELS = [
    m.strip()
    for m in os.getenv("GEMINI_MODELS", "gemini-3.5-flash,gemini-2.5-flash,gemini-3.5-flash-lite").split(",")
    if m.strip()
]
GEMINI_MAX_TOOL_CALLS = _int("GEMINI_MAX_TOOL_CALLS", 6)


def _models(name: str, default: str) -> list[str]:
    return [m.strip() for m in os.getenv(name, default).split(",") if m.strip()]


# Voice: speech-to-text (any audio-capable model) and text-to-speech (Interactions API).
GEMINI_STT_MODELS = _models("GEMINI_STT_MODELS", "gemini-3.5-flash-lite,gemini-2.5-flash")
GEMINI_TTS_MODELS = _models("GEMINI_TTS_MODELS", "gemini-3.8-flash-tts,gemini-3.8-flash-lite-tts")
# One of Gemini's 30 prebuilt voices, e.g. Kore, Puck, Aoede, Charon, Leda.
GEMINI_TTS_VOICE = os.getenv("GEMINI_TTS_VOICE", "Kore")
# Spoken answers favour speed: flash-lite answers in a few seconds and has the most free quota.
GEMINI_VOICE_MODELS = _models("GEMINI_VOICE_MODELS", "gemini-3.5-flash-lite,gemini-3.5-flash,gemini-2.5-flash")
# Fewer tool rounds for spoken answers; each round is another model request (1-10 s on the free tier).
GEMINI_VOICE_MAX_TOOL_CALLS = _int("GEMINI_VOICE_MAX_TOOL_CALLS", 3)
# Thinking level for spoken answers on Gemini 3 models ("" = model default). Lower is faster.
GEMINI_VOICE_THINKING = os.getenv("GEMINI_VOICE_THINKING", "low")
# After a model says it is out of quota (429), skip it for this many seconds instead of
# waiting on a failed request every time. Busy models (5xx) are skipped for 30 seconds.
GEMINI_COOLDOWN_S = _float("GEMINI_COOLDOWN_S", 300.0)
# How long /api/speech waits for a part's audio before the app falls back to the phone's voice.
SPEECH_WAIT_S = _float("SPEECH_WAIT_S", 25.0)
VOICE_MAX_UPLOAD_MB =_float("VOICE_MAX_UPLOAD_MB", 4.0)
RATE_LIMIT_SPEECH_PER_MIN = _int("RATE_LIMIT_SPEECH_PER_MIN", 40)  # GET /api/speech/<id>

# ── Access control ───────────────────────────────────────────────────────────
# Optional shared key. If set, every /api/* request (except health) must send
# the same value in the X-API-Key header. It ships inside the app, so it only
# stops casual use of your Gemini quota; the rate limits below do the real work.
APP_API_KEY = os.getenv("APP_API_KEY", "")
RATE_LIMIT_AI_PER_MIN = _int("RATE_LIMIT_AI_PER_MIN", 8)  # /api/chat, /api/explain
RATE_LIMIT_PER_MIN = _int("RATE_LIMIT_PER_MIN", 60)  # everything else

# ── Battery / range (same defaults as AI/Algorithm/config.py) ────────────────
DEFAULT_CAPACITY_KWH = _float("DEFAULT_CAPACITY_KWH", 60.0)
DEFAULT_WH_PER_KM = _float("DEFAULT_WH_PER_KM", 180.0)
RANGE_SAFETY_FACTOR = _float("RANGE_SAFETY_FACTOR", 0.85)
STOPPING_THRESHOLD_WH = 0.1

# ── Ranking (mirrors Calculation_Model.total_score in AI/Algorithm/logic.py) ─
# POI is not used, so its 0.25 is split evenly across the other three factors.
WEIGHT_DISTANCE = _float("WEIGHT_DISTANCE", 1 / 3)
WEIGHT_WAIT = _float("WEIGHT_WAIT", 1 / 3)
WEIGHT_COST = _float("WEIGHT_COST", 1 / 3)
CANDIDATE_LIMIT = _int("CANDIDATE_LIMIT", 25)  # nearest reachable stations that get scored
MAX_SEARCH_RADIUS_KM = _float("MAX_SEARCH_RADIUS_KM", 40.0)  # same cap as the app

# Placeholder until Model A/B are finished (see wait_model.py).
WAIT_PLACEHOLDER_MIN = _float("WAIT_PLACEHOLDER_MIN", 0.0)

# ── Road distance ────────────────────────────────────────────────────────────
OSRM_URL = os.getenv("OSRM_URL", "https://router.project-osrm.org")
OSRM_TIMEOUT_S = _float("OSRM_TIMEOUT_S", 6.0)
# Used when OSRM is unreachable: straight line × this factor ≈ road distance.
ROAD_DETOUR_FACTOR = _float("ROAD_DETOUR_FACTOR", 1.3)
