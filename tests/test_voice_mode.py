# tests/test_voice_mode.py
"""Voice mode (Phase 2) — VAD engine, WS route contract, settings, client JS.

Voice mode is the hands-free dictation edge: browser mic → WS
/api/voice/stream → Silero VAD → STT → composer. Tests cover the VAD
service on a small real-speech fixture (tests/fixtures/
voice_mode_speech.wav, TTS-generated English), the WebSocket route
contract with a stub STT service, the new settings keys, the STT
CUDA-OOM→CPU fallback, and (via node) the client JS modules.
"""

import io
import json
import wave
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "voice_mode_speech.wav"

pytest.importorskip("onnxruntime")

from services.vad.silero_vad import (  # noqa: E402
    SAMPLE_RATE, SileroVAD, VadConfig, detect_speech,
)

SILENCE = b"\x00\x00" * SAMPLE_RATE


def _fixture_pcm16() -> bytes:
    """Fixture resampled to 16 kHz PCM16 mono (the VAD input format)."""
    w = wave.open(str(FIXTURE))
    assert w.getnchannels() == 1 and w.getsampwidth() == 2
    src = w.getframerate()
    pcm = w.readframes(w.getnframes())
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    t = np.linspace(0, len(x) / src, int(len(x) / src * SAMPLE_RATE))
    y = np.interp(t, np.arange(len(x)) / src, x).astype(np.int16)
    return y.tobytes()


def _wav_len(data: bytes) -> float:
    w = wave.open(io.BytesIO(data))
    return w.getnframes() / w.getframerate()


# ── VAD engine ──

def test_vad_single_utterance_with_pre_roll():
    speech = _fixture_pcm16()
    segs = detect_speech(SILENCE + speech + SILENCE)
    assert len(segs) == 1, segs
    s = segs[0]
    # Starts ~1 s in (after the leading silence), within the pre-roll window.
    assert 0.8 < s["start"] < 1.4
    assert 2.5 < _wav_len(s["audio"]) < 4.5


def test_vad_two_utterances_split_on_silence():
    speech = _fixture_pcm16()
    stream = SILENCE + speech + SILENCE * 2 + speech + SILENCE * 2
    segs = detect_speech(stream)
    assert len(segs) == 2, segs
    # Second segment starts inside/after the 2 s gap (its start may reach
    # back up to speech_pad_ms=300 ms into the gap by design).
    assert segs[1]["start"] > segs[0]["end"] + 1.0
    for s in segs:
        assert 2.5 < _wav_len(s["audio"]) < 4.5


def test_vad_streaming_matches_batch():
    speech = _fixture_pcm16()
    stream = SILENCE + speech + SILENCE * 2 + speech + SILENCE * 2
    vad = SileroVAD()
    events = []
    frame = 640  # 20 ms @ 16 kHz — the client's frame size
    for i in range(0, len(stream), frame * 2):
        events.extend(vad.feed(stream[i:i + frame * 2]))
    events.extend(vad.flush())
    assert [e["event"] for e in events] == ["start", "stop", "start", "stop"]
    for e in events:
        if e["event"] == "stop":
            assert 2.5 < _wav_len(e["audio"]) < 4.5


def test_vad_streaming_irregular_frames():
    speech = _fixture_pcm16()
    stream = SILENCE + speech + SILENCE * 2 + speech
    vad = SileroVAD()
    events = []
    i = 0
    while i < len(stream):
        step = (i % 5) * 1024 + 321  # deliberately awkward sizes
        events.extend(vad.feed(stream[i:i + step]))
        i += step
    events.extend(vad.flush())
    assert [e["event"] for e in events] == ["start", "stop", "start", "stop"]


def test_vad_blip_dropped():
    speech = _fixture_pcm16()
    blip = speech[: int(0.2 * SAMPLE_RATE) * 2]  # 200 ms < 250 ms minimum
    assert detect_speech(SILENCE + blip + SILENCE) == []


def test_vad_pure_silence_no_events():
    vad = SileroVAD()
    assert vad.feed(SILENCE * 3) + vad.flush() == []


def test_vad_config_min_silence_controls_split():
    speech = _fixture_pcm16()
    stream = SILENCE + speech + SILENCE + speech + SILENCE
    # A 3 s silence tail must NOT split across the 1 s gap.
    segs = detect_speech(stream, VadConfig(min_silence_ms=3000))
    assert len(segs) == 1


def test_vad_wav_is_decodable():
    speech = _fixture_pcm16()
    segs = detect_speech(SILENCE + speech + SILENCE)
    assert len(segs) == 1
    w = wave.open(io.BytesIO(segs[0]["audio"]))
    assert w.getframerate() == SAMPLE_RATE
    assert w.getnchannels() == 1
    assert w.getsampwidth() == 2


# ── WebSocket route contract (stub STT) ──

class _StubSTT:
    def __init__(self, available=True, text="hello there", provider="local"):
        self.available = available
        self._text = text
        self._provider = provider
        self.calls = []

    def get_stats(self):
        return {"available": self.available, "provider": self._provider}

    def transcribe(self, audio: bytes, **kw):
        self.calls.append(len(audio))
        return self._text


class _NoAuthManager:
    def validate_token(self, token):
        return token == "good-token"


class _SlowStatsSTT:
    """get_stats would block on a real model load — the status endpoint
    must not touch it (regression: event-loop stall on every page load)."""
    available = True

    def get_stats(self):
        import time
        time.sleep(1.0)
        return {"available": True, "provider": "local"}

    def transcribe(self, audio: bytes, **kw):
        return "x"


@pytest.fixture
def voice_app(monkeypatch):
    """Factory: (stt, voice_enabled, auth_manager) → FastAPI app with the
    voice router and controllable settings."""
    from fastapi import FastAPI
    from routes.voice_routes import setup_voice_routes
    from src import settings as S

    def make(stt, voice_enabled=True, auth_manager=None, extra=None):
        app = FastAPI()
        app.include_router(setup_voice_routes(stt))
        app.state.auth_manager = auth_manager
        # Mirror a configured instance: STT on with the local provider.
        base = {**S.DEFAULT_SETTINGS,
                "voice_mode_enabled": voice_enabled,
                "stt_enabled": True, "stt_provider": "local",
                **(extra or {})}
        monkeypatch.setattr(S, "load_settings", lambda: dict(base))
        monkeypatch.setattr(S, "get_setting",
                            lambda k, d=None: base.get(k, d))
        return app
    return make


def _send_ws(ws, pcm: bytes, frame_samples=640):
    for i in range(0, len(pcm), frame_samples * 2):
        ws.send_bytes(pcm[i:i + frame_samples * 2])


def test_ws_rejects_when_voice_mode_disabled(voice_app):
    from fastapi.testclient import TestClient
    stt = _StubSTT()
    app = voice_app(stt, voice_enabled=False)
    with TestClient(app).websocket_connect("/api/voice/stream") as ws:
        data = ws.receive_json()
        assert data["error"]["code"] == "voice_mode_disabled"
        # Server closes (4001) — further receive raises.
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_ws_rejects_when_stt_unavailable(voice_app):
    from fastapi.testclient import TestClient
    app = voice_app(_StubSTT(available=False), voice_enabled=True)
    with TestClient(app).websocket_connect("/api/voice/stream") as ws:
        data = ws.receive_json()
        assert data["error"]["code"] == "stt_unavailable"


def test_ws_transcribes_speech_after_silence(voice_app):
    from fastapi.testclient import TestClient
    stt = _StubSTT(text="do you hear me clearly")
    app = voice_app(stt, voice_enabled=True)
    with TestClient(app).websocket_connect("/api/voice/stream") as ws:
        ready = ws.receive_json()
        assert ready["status"] == "ready"
        assert ready["sample_rate"] == SAMPLE_RATE
        # 1 s of silence must not reach STT, then the fixture speech must.
        _send_ws(ws, SILENCE)
        _send_ws(ws, _fixture_pcm16())
        _send_ws(ws, SILENCE)  # silence tail → VAD stop (the fixture ends on a word)
        saw_vad_start = saw_stt_start = False
        got = None
        for _ in range(8):
            m = ws.receive_json()
            if m.get("vad") == "start":
                saw_vad_start = True
            elif m.get("stt") == "start":
                saw_stt_start = True
            elif "transcript" in m:
                got = m
                break
        assert saw_vad_start and saw_stt_start
        assert got is not None
        assert got["transcript"] == "do you hear me clearly"
        assert got["audio_ms"] > 2000
        assert len(stt.calls) == 1  # exactly one STT call


def test_ws_gap_flush_on_quiet_stream(voice_app):
    """Speech with NO silence tail: the stream itself goes quiet (tab
    suspended / mic cut). The server must flush the in-flight utterance
    after ~1 s instead of waiting for a silence tail forever."""
    from fastapi.testclient import TestClient
    stt = _StubSTT(text="in flight")
    app = voice_app(stt, voice_enabled=True)
    with TestClient(app).websocket_connect("/api/voice/stream") as ws:
        assert ws.receive_json()["status"] == "ready"
        _send_ws(ws, _fixture_pcm16())  # no trailing silence
        # No more frames — the receive timeout (0.5 s) + FLUSH_AFTER_S (1 s)
        # must produce a flush transcript.
        got = None
        for _ in range(12):
            m = ws.receive_json()
            if "transcript" in m:
                got = m
                break
        assert got is not None
        assert got["transcript"] == "in flight"
        assert got["reason"] == "flush"
        assert len(stt.calls) == 1


def test_ws_silence_only_no_transcript(voice_app):
    from fastapi.testclient import TestClient
    stt = _StubSTT()
    app = voice_app(stt, voice_enabled=True)
    with TestClient(app).websocket_connect("/api/voice/stream") as ws:
        assert ws.receive_json()["status"] == "ready"
        _send_ws(ws, SILENCE * 2)  # 2 s of silence
        ws.close()
    assert stt.calls == []


def test_ws_requires_auth_when_auth_enabled(voice_app, monkeypatch):
    from fastapi.testclient import TestClient
    import src.owner_identity as oi
    monkeypatch.setattr(oi, "auth_disabled", lambda: False)
    app = voice_app(_StubSTT(), voice_enabled=True,
                    auth_manager=_NoAuthManager())
    with TestClient(app).websocket_connect("/api/voice/stream") as ws:
        # No cookie → server closes 4401 without a "ready" frame.
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
    assert exc_info.value.code == 4401


def test_ws_auth_ok_with_session_cookie(voice_app, monkeypatch):
    from fastapi.testclient import TestClient
    import src.owner_identity as oi
    monkeypatch.setattr(oi, "auth_disabled", lambda: False)
    app = voice_app(_StubSTT(), voice_enabled=True,
                    auth_manager=_NoAuthManager())
    with TestClient(app).websocket_connect(
            "/api/voice/stream",
            cookies={"odysseus_session": "good-token"}) as ws:
        assert ws.receive_json()["status"] == "ready"


def test_status_endpoint(voice_app):
    from fastapi.testclient import TestClient
    stt = _StubSTT(available=True, provider="local")
    app = voice_app(stt, voice_enabled=True)
    r = TestClient(app).get("/api/voice/status")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["stt_available"] is True
    assert body["stt_provider"] == "local"
    assert body["vad_silence_ms"] == 500


def test_status_is_settings_only_and_fast(voice_app):
    import time
    from fastapi.testclient import TestClient
    stt = _SlowStatsSTT()
    app = voice_app(stt, voice_enabled=True)
    t0 = time.monotonic()
    r = TestClient(app).get("/api/voice/status")
    assert r.status_code == 200
    assert r.json()["stt_available"] is True
    # Must be settings-only: the stub's get_stats sleeps 1 s; a stall would
    # also mean the real Whisper load (~5 s) ran on the event loop.
    assert time.monotonic() - t0 < 0.8


def test_ws_rejects_browser_provider(voice_app):
    from fastapi.testclient import TestClient
    stt = _StubSTT(available=True, provider="browser")
    app = voice_app(stt, voice_enabled=True,
                    extra={"stt_provider": "browser"})
    with TestClient(app).websocket_connect("/api/voice/stream") as ws:
        data = ws.receive_json()
        assert data["error"]["code"] == "stt_unavailable"


# ── settings ──

def test_settings_defaults_inert():
    from src.settings import DEFAULT_SETTINGS
    assert DEFAULT_SETTINGS["voice_mode_enabled"] is False
    assert DEFAULT_SETTINGS["stt_enabled"] is False
    assert DEFAULT_SETTINGS["vad_silence_ms"] == 500
    assert DEFAULT_SETTINGS["vad_min_speech_ms"] == 250


def test_settings_save_roundtrip_voice_keys(tmp_path, monkeypatch):
    """The generic /api/auth/settings POST persists the new voice keys
    (they must be in DEFAULT_SETTINGS for the endpoint to accept them)."""
    import src.settings as S
    from routes import auth_routes as AR
    from fastapi.testclient import TestClient

    stored = {**S.DEFAULT_SETTINGS}
    monkeypatch.setattr(AR, "_load_settings", lambda: dict(stored))
    monkeypatch.setattr(
        AR, "_save_settings",
        lambda d: (stored.update(d), S._invalidate_caches()))

    class _AdminAuth:
        is_configured = True
        def is_admin(self, u):
            return True
        def get_username_for_token(self, token):
            return "admin" if token == "t" else None

    import fastapi
    app = fastapi.FastAPI()
    app.include_router(AR.setup_auth_routes(_AdminAuth()))
    client = TestClient(app)
    r = client.post("/api/auth/settings",
                    json={"voice_mode_enabled": True,
                          "vad_silence_ms": 600},
                    cookies={"odysseus_session": "t"})
    assert r.status_code == 200
    assert r.json()["voice_mode_enabled"] is True
    assert stored["voice_mode_enabled"] is True
    assert stored["vad_silence_ms"] == 600


# ── STT CUDA-OOM → CPU fallback ──

def test_stt_cuda_oom_falls_back_to_cpu(monkeypatch):
    import faster_whisper
    import torch
    from services.stt import stt_service as stt_mod
    import src.settings as S

    loads = []

    class _FakeModel:
        def __init__(self, size, device, compute_type):
            self.device = device

    def fake_whisper_model(size, device, compute_type):
        loads.append((device, compute_type))
        if device == "cuda":
            raise RuntimeError("out of memory")
        return _FakeModel(size, device, compute_type)

    monkeypatch.setattr(faster_whisper, "WhisperModel", fake_whisper_model)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(S, "load_settings", lambda: {
        "stt_enabled": True, "stt_provider": "local",
        "stt_model": "base", "stt_language": ""})

    svc = stt_mod.STTService()
    svc._whisper_model = None
    m = svc._get_whisper()
    assert m is not None
    assert loads == [("cuda", "float16"), ("cpu", "int8")]
    assert svc.available is True


# ── client JS (node smoke tests) ──

def test_client_js_modules_load():
    node = REPO_ROOT / "tests" / "helpers" / "check_client_js.mjs"
    r = _run_node(node)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "voiceMode OK" in r.stdout


def test_pcm_processor_decimates_correctly():
    node = REPO_ROOT / "tests" / "helpers" / "check_pcm_processor.mjs"
    r = _run_node(node)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "pcm16 OK" in r.stdout


def _run_node(script):
    import subprocess
    return subprocess.run(["node", str(script)], cwd=str(REPO_ROOT),
                          capture_output=True, text=True, timeout=120)
