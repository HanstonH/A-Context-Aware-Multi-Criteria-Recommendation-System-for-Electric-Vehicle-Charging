"""Offline tests for /api/voice and /api/speech: Gemini STT, chat and TTS are faked."""

import io
import json

import pytest

from backend import server, voice
from backend.server import _hits, app

WHERE = {"lat": 25.0478, "lng": 121.5170, "battery_pct": 40, "lang": "zh"}
FAKE_WAV = b"RIFF" + b"\0" * 2000


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

    monkeypatch.setattr(server, "chat", fake_chat)
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


def test_audio_mime():
    assert voice.audio_mime("audio/x-m4a", "a.m4a") == "audio/m4a"
    assert voice.audio_mime("application/octet-stream", "rec.m4a") == "audio/m4a"
    assert voice.audio_mime("audio/3gpp", "a.3gp") is None
    # Android may label an .m4a recording as audio/mpeg; the extension decides.
    assert voice.audio_mime("audio/mpeg", "recording-123.m4a") == "audio/m4a"
    assert voice.audio_mime("audio/aac", "") == "audio/aac"
