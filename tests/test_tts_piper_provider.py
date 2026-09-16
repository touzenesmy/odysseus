"""Piper (local CPU) TTS provider — unit + route contract.

The provider resolves voices from a flat cache dir of .onnx files
(default ~/.cache/piper-voices, override ODYSSEUS_PIPER_VOICE_DIR).
No real voice is loaded here: _get_piper_voice is monkeypatched with a
stub that mimics piper 1.8's PiperVoice surface
(synthesize() -> iterable of chunks with .audio_int16_bytes,
config.sample_rate).
"""

import types
from types import SimpleNamespace

import pytest

from services.tts.tts_service import TTSService


class _FakeChunk:
    def __init__(self, audio_int16_bytes):
        self.audio_int16_bytes = audio_int16_bytes


class _FakePiperVoice:
    """Mimics the piper 1.8 PiperVoice surface used by _synthesize_piper."""

    def __init__(self):
        self.config = SimpleNamespace(sample_rate=22050)
        self.calls = 0
        self.last_config = "unset"

    def synthesize(self, text, syn_config=None, include_alignments=False):
        self.calls += 1
        self.last_config = syn_config
        yield _FakeChunk(b"\x00\x01" * 1102)  # ~50 ms @ 22050 Hz


def _make_service(tmp_path, voice_names=(), monkeypatch=None):
    cache = tmp_path / "piper-voices"
    cache.mkdir()
    for name in voice_names:
        (cache / f"{name}.onnx").write_bytes(b"fake onnx")
    if monkeypatch:
        monkeypatch.setattr(TTSService, "_piper_voice_dir",
                            lambda self: cache)
    return TTSService(cache_dir=str(tmp_path / "tts-cache"))


def _settings(provider="piper", voice="en_US-test-medium", enabled=True):
    return {
        "tts_enabled": enabled,
        "tts_provider": provider,
        "tts_model": "piper",
        "tts_voice": voice,
        "tts_speed": "1",
    }


# ── availability ──

def test_available_true_when_voice_cached(tmp_path, monkeypatch):
    service = _make_service(tmp_path, ["en_US-test-medium"], monkeypatch)
    monkeypatch.setattr(service, "_load_settings", lambda: _settings())
    assert service.available is True


def test_available_false_when_voice_missing(tmp_path, monkeypatch):
    service = _make_service(tmp_path, ["en_US-other-medium"], monkeypatch)
    monkeypatch.setattr(service, "_load_settings", lambda: _settings())
    assert service.available is False


def test_available_tolerates_non_string_piper_voice(tmp_path, monkeypatch):
    # A corrupt settings.json can store a non-string tts_voice; the
    # availability check must not raise (same contract as provider values).
    service = _make_service(tmp_path, ["en_US-test-medium"], monkeypatch)
    monkeypatch.setattr(service, "_load_settings",
                        lambda: _settings(voice=None))
    assert service.available is False


# ── voice name sanitization ──

def test_voice_path_rejects_path_shaped_names(tmp_path, monkeypatch):
    service = _make_service(tmp_path, [], monkeypatch)
    for bad in ("../piper-voices", "a/b", "..", ".hidden", "~user", "/abs/x",
                "", "   "):
        assert service._piper_voice_path(bad) is None, bad


# ── voice listing ──

def test_list_voices_reads_sidecar_meta(tmp_path, monkeypatch):
    import json
    service = _make_service(tmp_path, ["en_US-lessac-medium"], monkeypatch)
    meta = {
        "language": {"code": "en_US", "name_english": "English",
                     "name_native": "English"},
        "audio": {"sample_rate": 22050, "quality": "medium"},
    }
    (tmp_path / "piper-voices" / "en_US-lessac-medium.onnx.json").write_text(
        json.dumps(meta))
    voices = service.list_piper_voices()
    assert voices == [{
        "name": "en_US-lessac-medium",
        "language": "English",
        "locale": "en_US",
        "quality": "medium",
        "sample_rate": 22050,
    }]


def test_list_voices_tolerates_missing_or_malformed_sidecar(tmp_path, monkeypatch):
    service = _make_service(tmp_path, ["en_US-nojson", "fr_FR-badjson"],
                            monkeypatch)
    (tmp_path / "piper-voices" / "fr_FR-badjson.onnx.json").write_text(
        "{not json")
    voices = service.list_piper_voices()
    names = {v["name"] for v in voices}
    assert names == {"en_US-nojson", "fr_FR-badjson"}
    by_name = {v["name"]: v for v in voices}
    assert by_name["en_US-nojson"]["language"] == "en_US-nojson"  # fallback
    assert by_name["fr_FR-badjson"]["quality"] == ""


def test_list_voices_empty_when_dir_absent(tmp_path, monkeypatch):
    service = _make_service(tmp_path, [], monkeypatch)
    (tmp_path / "piper-voices").rmdir()
    assert service.list_piper_voices() == []


# ── synthesis + cache ──

def _stub_voice(service, monkeypatch):
    fake = _FakePiperVoice()
    monkeypatch.setattr(service, "_get_piper_voice", lambda voice: fake)
    return fake


def test_synthesize_piper_returns_wav_and_caches(tmp_path, monkeypatch):
    service = _make_service(tmp_path, ["en_US-test-medium"], monkeypatch)
    fake = _stub_voice(service, monkeypatch)
    monkeypatch.setattr(service, "_load_settings", lambda: _settings())
    audio = service.synthesize("hello world")
    assert audio is not None and audio[:4] == b"RIFF"
    assert fake.calls == 1
    # Second call is a cache hit — no second synthesis.
    assert service.synthesize("hello world") == audio
    assert fake.calls == 1


def test_synthesize_piper_voice_override_and_separate_cache(tmp_path, monkeypatch):
    service = _make_service(tmp_path, ["en_US-test-medium",
                                       "en_US-other-medium"], monkeypatch)
    fake = _stub_voice(service, monkeypatch)
    monkeypatch.setattr(service, "_load_settings", lambda: _settings())
    a = service.synthesize("same text")
    b = service.synthesize("same text", voice="en_US-other-medium")
    assert a is not None and b is not None
    assert fake.calls == 2  # different voice -> different cache key
    # And the overridden voice is not what the default call used.
    assert service.synthesize("same text") == a
    assert fake.calls == 2


def test_synthesize_piper_speed_one_skips_config(tmp_path, monkeypatch):
    service = _make_service(tmp_path, ["en_US-test-medium"], monkeypatch)
    fake = _stub_voice(service, monkeypatch)
    monkeypatch.setattr(service, "_load_settings", lambda: _settings())
    assert service.synthesize("hi") is not None
    assert fake.last_config is None  # 1.0x -> Piper voice defaults


def test_synthesize_piper_speed_maps_to_length_scale(tmp_path, monkeypatch):
    pytest.importorskip("piper")  # SynthesisConfig only exists with piper
    service = _make_service(tmp_path, ["en_US-test-medium"], monkeypatch)
    fake = _stub_voice(service, monkeypatch)
    monkeypatch.setattr(service, "_load_settings",
                        lambda: _settings() | {"tts_speed": "1.5"})
    assert service.synthesize("hi") is not None
    assert fake.last_config is not None
    assert abs(fake.last_config.length_scale - 1.0 / 1.5) < 1e-9


def test_synthesize_piper_unavailable_voice_returns_none(tmp_path, monkeypatch):
    service = _make_service(tmp_path, [], monkeypatch)
    monkeypatch.setattr(service, "_get_piper_voice", lambda voice: None)
    monkeypatch.setattr(service, "_load_settings",
                        lambda: _settings(voice="nope"))
    assert service.synthesize("hi") is None


# ── route contract ──

def test_routes_voices_and_voice_override(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes.tts_routes import setup_tts_routes

    service = _make_service(tmp_path, ["en_US-a-medium", "fr_FR-b-medium"],
                            monkeypatch)
    calls = []

    class _Stub:
        available = True
        def list_piper_voices(self):
            return service.list_piper_voices()
        def synthesize(self, text, use_cache=True, voice=None):
            calls.append((text, voice))
            return b"RIFF" + b"\x00" * 4
        def synthesize_to_base64(self, text, voice=None):
            calls.append((text, voice))
            return "aW5kZXg="

    app = FastAPI()
    app.include_router(setup_tts_routes(_Stub()))
    client = TestClient(app)

    r = client.get("/api/tts/voices")
    assert r.status_code == 200
    names = [v["name"] for v in r.json()["voices"]]
    assert names == ["en_US-a-medium", "fr_FR-b-medium"]

    r = client.post("/api/tts/synthesize",
                    json={"text": "hello", "format": "base64",
                          "voice": "fr_FR-b-medium"})
    assert r.status_code == 200
    assert r.json() == {"audio": "aW5kZXg="}
    assert calls[-1] == ("hello", "fr_FR-b-medium")

    r = client.post("/api/tts/synthesize", json={"text": "hi"})
    assert r.status_code == 200
    assert calls[-1] == ("hi", None)
