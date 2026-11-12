"""HTTP API for the MapExplore app. Run with gunicorn (see gunicorn.conf.py)."""

from __future__ import annotations

import hmac
import json
import logging
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from functools import wraps

from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException

from . import config
from .algorithm import estimate_range, recommend
from .assistant import AssistantUnavailable, ChatContext, chat, explain, recommendations
from .data import store
from .geo import resolve_city
from .voice import SpeechFailed, audio_mime, get_speech, speakable, start_speech, transcribe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("backend")

app = Flask(__name__)
app.json.ensure_ascii = False
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024


class BadRequest(ValueError):
    pass


@app.errorhandler(BadRequest)
def _bad_request(exc):
    return jsonify({"ok": False, "error": str(exc)}), 400


@app.errorhandler(Exception)
def _server_error(exc):
    if isinstance(exc, HTTPException):  # 404, 405, 413 ...
        return jsonify({"ok": False, "error": exc.description or exc.name}), exc.code
    log.exception("Unhandled error: %s", exc)
    return jsonify({"ok": False, "error": "server error"}), 500


# ── Access control ───────────────────────────────────────────────────────────

_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_hits_lock = threading.Lock()


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.remote_addr or "?")


def guarded(bucket: str, per_min: int):
    """Require the shared API key (if configured) and apply a per-IP rate limit."""

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if config.APP_API_KEY and not hmac.compare_digest(
                request.headers.get("X-API-Key", ""), config.APP_API_KEY
            ):
                return jsonify({"ok": False, "error": "invalid API key"}), 401
            key = (bucket, _client_ip())
            now = time.monotonic()
            with _hits_lock:
                q = _hits[key]
                while q and now - q[0] > 60:
                    q.popleft()
                if len(q) >= per_min:
                    retry = int(60 - (now - q[0])) + 1
                    resp = jsonify({"ok": False, "error": "rate limited", "retry_after_s": retry})
                    resp.headers["Retry-After"] = str(retry)
                    return resp, 429
                q.append(now)
            return fn(*args, **kwargs)

        return wrapper

    return deco


# ── Input helpers ────────────────────────────────────────────────────────────


def _body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest("Send a JSON object.")
    return data


def _num(data: dict, key: str, *, lo: float, hi: float, default: float | None = None) -> float:
    raw = data.get(key, default)
    if raw is None:
        raise BadRequest(f"'{key}' is required.")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise BadRequest(f"'{key}' must be a number.") from None
    if not lo <= value <= hi:
        raise BadRequest(f"'{key}' must be between {lo} and {hi}.")
    return value


def _context(data: dict) -> ChatContext:
    lang = data.get("lang", "en")
    return ChatContext(
        lat=_num(data, "lat", lo=-90, hi=90),
        lng=_num(data, "lng", lo=-180, hi=180),
        battery_pct=_num(data, "battery_pct", lo=0, hi=100),
        lang="zh" if lang == "zh" else "en",
        capacity_kwh=_num(data, "capacity_kwh", lo=5, hi=250, default=config.DEFAULT_CAPACITY_KWH),
        wh_per_km=_num(data, "wh_per_km", lo=50, hi=600, default=config.DEFAULT_WH_PER_KM),
        dest_id=str(data["dest_id"])[:64] if data.get("dest_id") else None,
    )


# ── Routes ───────────────────────────────────────────────────────────────────


@app.get("/")
@app.get("/api/health")
def health():
    return jsonify(
        {
            "ok": True,
            "stations": len(store().stations),
            "gemini": bool(config.GEMINI_API_KEY),
            "models": config.GEMINI_MODELS,
            "voice": {
                "stt": config.GEMINI_STT_MODELS,
                "tts": config.GEMINI_TTS_MODELS,
                "voice": config.GEMINI_TTS_VOICE,
            },
            "wait_model": "placeholder",
            "auth_required": bool(config.APP_API_KEY),
        }
    )


@app.post("/api/range")
@guarded("api", config.RATE_LIMIT_PER_MIN)
def range_estimate():
    ctx = _context({"lat": 0, "lng": 0, **_body()})
    return jsonify({"ok": True, "range": estimate_range(ctx.battery_pct, ctx.capacity_kwh, ctx.wh_per_km)})


@app.get("/api/stations/<station_id>")
@guarded("api", config.RATE_LIMIT_PER_MIN)
def station(station_id: str):
    d = store().details(station_id)
    if not d:
        return jsonify({"ok": False, "error": "station not found"}), 404
    return jsonify({"ok": True, "station": d})


@app.post("/api/recommend")
@guarded("api", config.RATE_LIMIT_PER_MIN)
def recommend_route():
    data = _body()
    ctx = _context(data)
    city = None
    if data.get("city"):
        city = resolve_city(str(data["city"]))
        if not city:
            raise BadRequest("Unknown city.")
    limit = int(_num(data, "limit", lo=1, hi=20, default=5))
    rec = recommend(
        ctx.lat,
        ctx.lng,
        ctx.battery_pct,
        capacity_kwh=ctx.capacity_kwh,
        wh_per_km=ctx.wh_per_km,
        city=city,
        limit=limit,
        lang=ctx.lang,
    )
    rec.pop("all_results", None)
    return jsonify(rec)


@app.post("/api/chat")
@guarded("ai", config.RATE_LIMIT_AI_PER_MIN)
def chat_route():
    data = _body()
    message = str(data.get("message") or "").strip()
    if not message:
        raise BadRequest("'message' is required.")
    history = _history(data)
    ctx = _context(data)
    try:
        result = chat(message[:2000], history, ctx)
    except AssistantUnavailable as exc:
        log.warning("Chat unavailable: %s", exc)
        return jsonify({"ok": False, "error": "assistant unavailable"}), 503
    return jsonify({"ok": True, **result})


def _history(data: dict) -> list[dict]:
    history = data.get("history") or []
    if not isinstance(history, list):
        raise BadRequest("'history' must be a list.")
    return [h for h in history if isinstance(h, dict)]


_prefetch_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="prefetch")


@app.post("/api/voice")
@guarded("ai", config.RATE_LIMIT_AI_PER_MIN)
def voice_route():
    """Spoken question in (multipart: 'audio' file + 'data' JSON), text answer + speech ids out."""
    request.max_content_length = int(config.VOICE_MAX_UPLOAD_MB * 1024 * 1024)
    upload = request.files.get("audio")
    if upload is None:
        raise BadRequest("Send the recording as the multipart field 'audio'.")
    try:
        data = json.loads(request.form.get("data") or "{}")
    except ValueError:
        raise BadRequest("'data' must be JSON.") from None
    if not isinstance(data, dict):
        raise BadRequest("'data' must be a JSON object.")
    ctx = _context(data)
    ctx.voice = True
    history = _history(data)
    mime = audio_mime(upload.mimetype, upload.filename)
    if not mime:
        raise BadRequest("Unsupported audio type; send m4a, aac, wav, mp3, ogg or webm.")
    audio = upload.read()
    if len(audio) < 1000:
        raise BadRequest("The recording is empty.")

    # Most spoken questions are "where should I charge?". Rank stations while the speech is
    # being transcribed (it takes longer), so Gemini can usually answer without a tool round trip.
    side = replace(ctx, seen={}, last_list=[])
    prefetch = _prefetch_pool.submit(recommendations, side, -1, None, 3)
    try:
        transcript = transcribe(audio, mime, ctx.lang)
        if not transcript:
            sorry = "抱歉，我沒聽清楚，請再說一次。" if ctx.lang == "zh" else "Sorry, I didn't catch that. Please say it again."
            return jsonify(
                {"ok": True, "heard": False, "transcript": "", "reply": sorry, "lang": ctx.lang, "stations": [], "speech": []}
            )
        try:
            ctx.prefetched = prefetch.result(timeout=5)
            ctx.remember(side.last_list)
        except Exception as exc:  # noqa: BLE001 - the tools can still fetch it
            log.warning("Voice prefetch failed: %s", exc)
        result = chat(transcript, history, ctx)
    except AssistantUnavailable as exc:
        log.warning("Voice unavailable: %s", exc)
        return jsonify({"ok": False, "error": "assistant unavailable"}), 503

    # "device": the app reads the reply with the phone's voice, so skip Gemini TTS (and its quota).
    speech = []
    if data.get("speech", "gemini") != "device":
        speech = [{**part, "url": f"/api/speech/{part['id']}"} for part in start_speech(result["reply"], ctx.lang)]
    spoken = speakable(result["reply"], ctx.lang)
    return jsonify({"ok": True, "heard": True, "transcript": transcript, **result, "spoken": spoken, "speech": speech})


@app.get("/api/speech/<speech_id>")
@guarded("speech", config.RATE_LIMIT_SPEECH_PER_MIN)
def speech_route(speech_id: str):
    """WAV audio for one part of a spoken reply (ids come from /api/voice, expire after 10 min)."""
    try:
        wav = get_speech(speech_id)
    except KeyError:
        return jsonify({"ok": False, "error": "unknown or expired speech id"}), 404
    except TimeoutError:
        return jsonify({"ok": False, "error": "speech is taking too long"}), 504
    except (SpeechFailed, AssistantUnavailable) as exc:
        log.warning("Speech %s failed: %s", speech_id, exc)
        return jsonify({"ok": False, "error": "speech failed"}), 502
    return Response(wav, mimetype="audio/wav", headers={"Cache-Control": "private, max-age=600"})


@app.post("/api/explain")
@guarded("ai", config.RATE_LIMIT_AI_PER_MIN)
def explain_route():
    data = _body()
    station_id = str(data.get("station_id") or "").strip()
    if not station_id:
        raise BadRequest("'station_id' is required.")
    if not store().get(station_id):
        return jsonify({"ok": False, "error": "station not found"}), 404
    result = explain(station_id, _context(data))
    if result is None:
        return jsonify({"ok": False, "error": "station could not be scored"}), 404
    return jsonify({"ok": True, **result})


# Load stations at import so the first request is fast and a missing DB fails the deploy.
store()
