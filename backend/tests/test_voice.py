"""Offline tests for /api/voice and /api/speech: Gemini STT, chat and TTS are faked."""

import io
import json

import pytest

from backend import assistant, server, voice
from backend.server import _hits, app

WHERE = {"lat": 25.0478, "lng": 121.5170, "battery_pct": 40, "lang": "zh"}
FAKE_WAV = b"RIFF" + b"\0" * 2000
REAL_SYNTHESIZE = voice.synthesize  # the fixture below replaces it with a fake


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    _hits.clear()
    calls = {"chat": [], "tts": []}

    def fake_chat(message, history, ctx):
        calls["chat"].append((message, history, ctx))
        return {"reply": "最近的是台北車站充電站，約 1.2 km。價格約 NT$12/kWh。到了再看卡片。", "stations": [], "model": "fake", "tools_used": []}

    def fake_tts(text):
        calls["tts"].append(text)
        return FAKE_WAV

    def fake_recommendations(ctx, battery_pct=-1, city=None, limit=5):
        top = {"id": "TPE0100", "name": "市民大道中林段停車場", "km": 0.6}
        ctx.remember([top])
        return {"results": [top]}

    monkeypatch.setattr(server, "chat", fake_chat)
    monkeypatch.setattr(server, "recommendations", fake_recommendations)
    monkeypatch.setattr(voice, "synthesize", fake_tts)
    return calls


def post_voice(client, audio=b"x" * 4000, data=WHERE, name="voice.m4a", mime="audio/m4a"):
    return client.post(
        "/api/voice",
        data={"audio": (io.BytesIO(audio), name, mime), "data": json.dumps(data)},
        content_type="multipart/form-data",
    )


def test_voice_round_trip(monkeypatch, fakes):
    monkeypatch.setattr(server, "transcribe", lambda audio, mime, lang: "附近哪裡可以充電")
    client = app.test_client()
    body = post_voice(client, data={**WHERE, "history": [{"role": "user", "text": "hi"}]}).get_json()
    assert body["ok"] and body["heard"] and body["transcript"] == "附近哪裡可以充電"
    message, history, ctx = fakes["chat"][0]
    assert ctx.voice and ctx.lang == "zh" and history == [{"role": "user", "text": "hi"}]
    # Stations were ranked while the speech was transcribed, and handed to the model.
    assert ctx.prefetched["results"][0]["id"] == "TPE0100" and "TPE0100" in ctx.seen
    assert body["speech"] and all(p["url"] == f"/api/speech/{p['id']}" for p in body["speech"])

    spoken = " ".join(p["text"] for p in body["speech"])
    assert "公里" in spoken and "新台幣" in spoken and "每度" in spoken and "km" not in spoken
    for part in body["speech"]:
        res = client.get(part["url"])
        assert res.status_code == 200 and res.mimetype == "audio/wav" and res.data == FAKE_WAV


def test_voice_accepts_expo_fetch_multipart(monkeypatch, fakes):
    """The exact body shape expo/fetch (Expo SDK 58) builds from FormData + expo-file-system File."""
    seen = {}

    def fake_transcribe(audio, mime, lang):
        seen.update(audio=audio, mime=mime)
        return "附近充電站"

    monkeypatch.setattr(server, "transcribe", fake_transcribe)
    boundary = "----ExpoFetchFormBoundary123"
    audio = bytes(range(256)) * 20
    body = (
        f"--{boundary}\r\n"
        'content-disposition: form-data; name="audio"; filename="recording-6f1c.m4a"\r\n'
        "content-type: audio/mpeg\r\n\r\n"
    ).encode() + audio + (
        f"\r\n--{boundary}\r\n"
        'content-disposition: form-data; name="data"\r\n\r\n'
        f"{json.dumps(WHERE)}\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    res = app.test_client().post(
        "/api/voice", data=body, content_type=f"multipart/form-data; boundary={boundary}"
    )
    assert res.status_code == 200 and res.get_json()["heard"]
    assert seen == {"audio": audio, "mime": "audio/m4a"}


def test_voice_no_speech_is_not_sent_to_chat(monkeypatch, fakes):
    monkeypatch.setattr(server, "transcribe", lambda audio, mime, lang: "")
    body = post_voice(app.test_client()).get_json()
    assert body["ok"] and body["heard"] is False and body["speech"] == [] and not fakes["chat"]


def test_voice_rejects_bad_uploads():
    client = app.test_client()
    assert client.post("/api/voice", data={"data": json.dumps(WHERE)}).status_code == 400
    assert post_voice(client, name="voice.3gp", mime="audio/3gpp").status_code == 400
    assert post_voice(client, audio=b"x").status_code == 400
    assert post_voice(client, data={"lat": 1}).status_code == 400
    too_big = b"x" * int((voice.config.VOICE_MAX_UPLOAD_MB + 1) * 1024 * 1024)
    assert post_voice(client, audio=too_big).status_code == 413


def test_speech_unknown_and_failed(monkeypatch):
    client = app.test_client()
    assert client.get("/api/speech/nope").status_code == 404

    def boom(text):
        raise voice.SpeechFailed("down")

    monkeypatch.setattr(voice, "synthesize", boom)
    part = voice.start_speech("Hello there, this is a test.", "en")[0]
    assert client.get(f"/api/speech/{part['id']}").status_code == 502


def test_split_for_speech_keeps_first_part_short():
    parts = voice.split_for_speech("好。最近的是 A 站，約兩公里。第二是 B 站。第三是 C 站。")
    assert len(parts) == 2 and parts[0].startswith("好。最近的是")
    assert voice.split_for_speech("") == []
    long = " ".join(f"Sentence number {i} is here." for i in range(40))
    assert len(voice.split_for_speech(long)) == 2
    assert len(voice.split_for_speech(long, max_parts=3)) == 3


def test_voice_device_speech_skips_gemini_tts(monkeypatch, fakes):
    monkeypatch.setattr(server, "transcribe", lambda audio, mime, lang: "附近哪裡可以充電")
    body = post_voice(app.test_client(), data={**WHERE, "speech": "device"}).get_json()
    assert body["speech"] == [] and not fakes["tts"]
    # The phone reads this version: units spelled out, no symbols.
    assert "新台幣" in body["spoken"] and "公里" in body["spoken"] and "NT$" not in body["spoken"]


def test_voice_still_answers_when_prefetch_fails(monkeypatch, fakes):
    def broken(*args, **kwargs):
        raise RuntimeError("routing down")

    monkeypatch.setattr(server, "recommendations", broken)
    monkeypatch.setattr(server, "transcribe", lambda audio, mime, lang: "附近哪裡可以充電")
    res = post_voice(app.test_client())
    assert res.status_code == 200 and res.get_json()["heard"]
    assert fakes["chat"][0][2].prefetched is None


def test_message_lang_follows_what_was_said():
    assert assistant.message_lang("Where is the nearest charger?", "zh") == "en"
    assert assistant.message_lang("附近哪裡可以充電", "en") == "zh"
    assert assistant.message_lang("Take me to 台北101", "zh") == "en"
    assert assistant.message_lang("去 Tesla 充電", "en") == "zh"
    assert assistant.message_lang("123 ?", "zh") == "zh"  # nothing to go on: keep the app's language


def test_cool_down_skips_models_out_of_quota(monkeypatch):
    monkeypatch.setattr(assistant, "_cooling", {})
    models = ["a", "b", "c"]
    assistant.cool_down("a", 429)
    assistant.cool_down("b", 400)  # a bad request says nothing about quota
    assert assistant.usable(models) == ["b", "c"]
    assistant.cool_down("b", 429)
    assistant.cool_down("c", 503)
    assert assistant.usable(models) == models  # all cooling: still try them all
    assert assistant.usable(models, all_if_none=False) == []


def test_busy_model_gets_a_second_try(monkeypatch):
    """Seen on Railway: flash-lite said "high demand" (503) once, then worked 0.6 s later."""
    from google.genai import errors

    monkeypatch.setattr(assistant, "_cooling", {})
    monkeypatch.setattr(assistant, "BUSY_RETRY_DELAY_S", 0)
    attempts = []

    def call(model):
        attempts.append(model)
        if model == "quota":
            raise errors.APIError(429, {"error": {"message": "quota"}})
        if attempts.count(model) == 1:
            raise errors.APIError(503, {"error": {"message": "high demand"}})
        return "ok"

    assert assistant.try_models(["lite", "quota"], call, "test") == ("ok", "lite")
    assert attempts == ["lite", "quota", "lite"]
    assert assistant.usable(["lite", "quota"]) == ["lite"]  # out of quota: skipped next time


def test_tts_fails_fast_when_every_voice_model_is_cooling(monkeypatch):
    monkeypatch.setattr(assistant, "_cooling", {})
    for model in voice.config.GEMINI_TTS_MODELS:
        assistant.cool_down(model, 429)
    monkeypatch.setattr(voice.config, "GEMINI_API_KEY", "test")
    with pytest.raises(voice.SpeechFailed, match="cooling down"):
        REAL_SYNTHESIZE("hello")  # raises before any request is sent


def test_audio_mime():
    assert voice.audio_mime("audio/x-m4a", "a.m4a") == "audio/m4a"
    assert voice.audio_mime("application/octet-stream", "rec.m4a") == "audio/m4a"
    assert voice.audio_mime("audio/3gpp", "a.3gp") is None
    # Android may label an .m4a recording as audio/mpeg; the extension decides.
    assert voice.audio_mime("audio/mpeg", "recording-123.m4a") == "audio/m4a"
    assert voice.audio_mime("audio/aac", "") == "audio/aac"
