"""Voice for the assistant: Gemini speech-to-text in, Gemini text-to-speech out.

Flow for one spoken question (see /api/voice in server.py):
1. transcribe() turns the phone's recording into text.
2. assistant.chat() answers it with the usual tools.
3. start_speech() splits the answer into a short first part and the rest and starts
   synthesizing them in the background. The app downloads each part from
   /api/speech/<id>, so it can start playing the first sentence while the rest is
   still being generated.
"""

from __future__ import annotations

import base64
import logging
import re
import secrets
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from google import genai
from google.genai import types

from . import config
from .assistant import AssistantUnavailable, cool_down, try_models, usable

log = logging.getLogger(__name__)

# Audio types Gemini accepts (docs: audio understanding). Phones send m4a (AAC).
SUPPORTED_AUDIO = {
    "audio/wav", "audio/mp3", "audio/aiff", "audio/aac", "audio/ogg", "audio/flac",
    "audio/mpeg", "audio/m4a", "audio/opus", "audio/webm",
}
_MIME_ALIASES = {
    "audio/x-m4a": "audio/m4a",
    "audio/mp4": "audio/m4a",
    "audio/mp4a-latm": "audio/m4a",
    "audio/x-wav": "audio/wav",
    "audio/wave": "audio/wav",
}
_EXT_MIME = {".m4a": "audio/m4a", ".mp4": "audio/m4a", ".aac": "audio/aac", ".wav": "audio/wav",
             ".mp3": "audio/mp3", ".ogg": "audio/ogg", ".webm": "audio/webm", ".flac": "audio/flac"}

NO_SPEECH = "<none>"


class SpeechFailed(RuntimeError):
    """Every TTS model failed for this piece of text."""


_clients: dict[str, genai.Client] = {}
_clients_lock = threading.Lock()


def _client(api_version: str | None = None) -> genai.Client:
    if not config.GEMINI_API_KEY:
        raise AssistantUnavailable("GEMINI_API_KEY is not set")
    key = api_version or "default"
    with _clients_lock:
        if key not in _clients:
            opts = types.HttpOptions(
                api_version=api_version,
                # No silent SDK retries: a rate-limited request can otherwise wait for its
                # retry-after while the driver hears nothing. We fall over to the next model.
                retry_options=types.HttpRetryOptions(attempts=1),
            )
            _clients[key] = genai.Client(api_key=config.GEMINI_API_KEY, http_options=opts)
        return _clients[key]


# ── Speech to text ───────────────────────────────────────────────────────────


def audio_mime(content_type: str | None, filename: str | None) -> str | None:
    """Normalize the upload's type to one Gemini accepts, or None if unsupported.

    The file extension wins: phones label .m4a recordings inconsistently
    (audio/mp4, audio/x-m4a, even audio/mpeg).
    """
    name = (filename or "").lower()
    for ext, ext_mime in _EXT_MIME.items():
        if name.endswith(ext):
            return ext_mime
    mime = (content_type or "").split(";")[0].strip().lower()
    mime = _MIME_ALIASES.get(mime, mime)
    return mime if mime in SUPPORTED_AUDIO else None


def transcribe(audio: bytes, mime: str, lang: str) -> str:
    """The driver's words as text, or "" if the recording has no clear speech."""
    script = (
        "Write Chinese in Traditional characters as used in Taiwan (繁體中文), never Simplified."
    )
    prompt = (
        "This is a driver speaking to the voice assistant of an EV charging app in Taiwan, "
        "in Mandarin Chinese or English, possibly with road noise. "
        f"Transcribe exactly what they say, in the language they speak. {script} "
        "Keep station and place names as spoken. Output only the transcript, with no quotes or notes. "
        f"If there is no intelligible speech, output exactly {NO_SPEECH}"
    )
    client = _client("v1beta")
    contents = [types.Part.from_bytes(data=audio, mime_type=mime), prompt]

    def call(model: str) -> types.GenerateContentResponse:
        cfg = types.GenerateContentConfig(temperature=0)
        if model.startswith("gemini-3"):  # transcribing needs no reasoning
            cfg.thinking_config = types.ThinkingConfig(thinking_level="minimal")
        return client.models.generate_content(model=model, contents=contents, config=cfg)

    resp, _ = try_models(config.GEMINI_STT_MODELS, call, "speech-to-text")
    text = (resp.text or "").strip().strip('"「」“”').strip()
    if not text or NO_SPEECH in text:
        return ""
    return text[:2000]


# ── Text to speech ───────────────────────────────────────────────────────────

_SENTENCE_END = re.compile(r"(?<=[。！？!?；;])|(?<=[.])(?=\s)")


def speakable(text: str, lang: str) -> str:
    """Turn a screen reply into something that sounds right when read aloud."""
    t = re.sub(r"[*#`_>|]+", " ", text)
    t = re.sub(r"(?m)^\s*(?:[-•]|\d+[.)])\s+", "", t)  # list markers
    if lang == "zh":
        t = re.sub(r"NT\$\s*", "新台幣", t)
        t = re.sub(r"\s*/\s*kWh", "每度", t)
        t = re.sub(r"(\d)\s*km\b", r"\1公里", t)
    else:
        t = re.sub(r"NT\$\s*([\d.]+)", r"\1 NT dollars", t)
        t = re.sub(r"\s*/\s*kWh", " per kilowatt-hour", t)
        t = re.sub(r"(\d)\s*km\b", r"\1 kilometres", t)
    return re.sub(r"\s+", " ", t).strip()


def split_for_speech(text: str, max_parts: int = 2) -> list[str]:
    """A short first part (so playback starts fast), then the rest.

    Each part is one TTS request, and free-tier quotas are small, so keep this at 2.
    """
    sentences = [s.strip() for s in _SENTENCE_END.split(text) if s and s.strip()]
    if not sentences:
        return []
    first = sentences.pop(0)
    while sentences and len(first) < 14:  # don't send a lonely "OK." on its own
        first += " " + sentences.pop(0) if first[-1:].isascii() else sentences.pop(0)
    parts = [first]
    rest = ""
    for s in sentences:
        joiner = " " if rest[-1:].isascii() else ""
        if rest and len(rest) + len(s) > 320 and len(parts) < max_parts - 1:
            parts.append(rest)
            rest = s
        else:
            rest = f"{rest}{joiner}{s}" if rest else s
    if rest:
        parts.append(rest)
    return parts


def synthesize(text: str) -> bytes:
    """WAV audio (24 kHz mono, 16-bit) for one piece of text."""
    client = _client("v1beta")
    last: Exception | None = None
    models = usable(config.GEMINI_TTS_MODELS, all_if_none=False)
    if not models:
        # Every voice model is out of quota: fail now so the app uses the phone's voice at once.
        raise SpeechFailed("text-to-speech models are cooling down after quota errors")
    for model in models:
        try:
            interaction = client.interactions.create(
                model=model,
                input=[
                    {
                        "type": "user_input",
                        "content": [
                            {
                                "type": "text",
                                "text": text,
                                "annotations": [
                                    {
                                        "type": "speech_metadata",
                                        "style": "calm, clear and friendly in-car assistant, moderate pace",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                response_format={"type": "audio", "mime_type": "audio/wav"},
                generation_config={"speech_config": [{"voice": config.GEMINI_TTS_VOICE}]},
            )
            data = interaction.output_audio.data
            audio = base64.b64decode(data) if isinstance(data, str) else bytes(data)
            if audio[:4] != b"RIFF":
                raise SpeechFailed(f"{model} returned non-WAV audio")
            return audio
        except Exception as exc:  # noqa: BLE001 - try the next model on any failure
            last = exc
            log.warning("TTS model %s failed: %s", model, str(exc)[:200])
            # The Interactions client raises its own error types; read the HTTP status either way.
            cool_down(model, getattr(exc, "code", None) or getattr(exc, "status_code", None))
    raise SpeechFailed(f"All text-to-speech models failed: {last}")


# Background synthesis, so /api/voice can answer before the audio is ready.
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tts")
_jobs: dict[str, tuple[float, Future]] = {}
_jobs_lock = threading.Lock()
_JOB_TTL_S = 600
_MAX_JOBS = 300


def start_speech(reply: str, lang: str) -> list[dict]:
    """Start synthesizing a reply; returns [{id, text}] in playback order."""
    parts = split_for_speech(speakable(reply, lang))
    out = []
    now = time.monotonic()
    with _jobs_lock:
        for key in [k for k, (born, _) in _jobs.items() if now - born > _JOB_TTL_S]:
            del _jobs[key]
        while len(_jobs) + len(parts) > _MAX_JOBS:
            del _jobs[next(iter(_jobs))]
        for part in parts:
            job_id = secrets.token_urlsafe(12)
            _jobs[job_id] = (now, _pool.submit(synthesize, part))
            out.append({"id": job_id, "text": part})
    return out


def get_speech(job_id: str, timeout_s: float | None = None) -> bytes:
    """Wait for one part's audio. KeyError if unknown or expired, SpeechFailed, TimeoutError."""
    with _jobs_lock:
        _, future = _jobs[job_id]
    try:
        return future.result(timeout=config.SPEECH_WAIT_S if timeout_s is None else timeout_s)
    except FutureTimeout:
        raise TimeoutError(job_id) from None
