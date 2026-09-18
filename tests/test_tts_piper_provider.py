"""Piper (local CPU) TTS provider — unit + route contract.

The provider resolves voices from a flat cache dir of .onnx files
(default ~/.cache/piper-voices, override ODYSSEUS_PIPER_VOICE_DIR).
No real voice is loaded here: _get_piper_voice is monkeypatched with a
stub that mimics piper 1.8's PiperVoice surface
(synthesize() -> iterable of chunks with .audio_int16_bytes,
config.sample_rate). The download path is tested with a fake httpx.stream
(no network): it must name the file, refuse bad sources, and leave no
partial file behind on failure.
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


# ── voice download (add_piper_voice) ──

class _FakeStreamResponse:
    """Mimics the httpx.stream(...) context manager used by add_piper_voice."""

    def __init__(self, payload: bytes, status: int = 200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=None, response=None
            )

    def iter_bytes(self, chunk_size: int = 65536):
        for i in range(0, len(self._payload), chunk_size):
            yield self._payload[i:i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _stub_httpx(monkeypatch, payload: bytes = b"data", status: int = 200,
                routes=None):
    """Stub httpx.stream. routes: list of (url_substring, payload, status)
    matched in order; anything unmatched gets the default payload/status."""
    calls = []

    def fake_stream(method, url, **kw):
        calls.append((method, url))
        for sub, pl, st in (routes or []):
            if sub in url:
                return _FakeStreamResponse(pl, st)
        return _FakeStreamResponse(payload, status)

    monkeypatch.setattr("services.tts.tts_service.httpx.stream", fake_stream)
    return calls


def test_piper_hf_url_builds_repo_path():
    from services.tts.tts_service import TTSService
    assert TTSService._piper_voice_hf_url("en_US-amy-medium") == (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
        "en/en_US/amy/medium/en_US-amy-medium.onnx"
    )


@pytest.mark.parametrize("bad", ["en_US", "a", "", "en_US-amy", "en_US-amy-"])
def test_piper_hf_url_rejects_malformed_names(bad):
    from services.tts.tts_service import TTSService
    with pytest.raises(ValueError):
        TTSService._piper_voice_hf_url(bad)


def test_add_piper_voice_from_link(tmp_path, monkeypatch):
    service = _make_service(tmp_path, [], monkeypatch)
    payload = b"fake-onnx-data" * 1000
    calls = _stub_httpx(monkeypatch, payload)
    res = service.add_piper_voice(
        "https://example.com/voices/en_US-new-high.onnx"
    )
    assert res["name"] == "en_US-new-high"
    assert (service._piper_voice_dir() / "en_US-new-high.onnx").read_bytes() == payload
    assert calls[0][1] == "https://example.com/voices/en_US-new-high.onnx"


def test_add_piper_voice_bare_name_uses_hf_repo(tmp_path, monkeypatch):
    service = _make_service(tmp_path, [], monkeypatch)
    calls = _stub_httpx(monkeypatch, b"data" * 100)
    res = service.add_piper_voice("en_US-amy-medium")
    assert res["name"] == "en_US-amy-medium"
    assert calls[0][1].endswith(
        "en/en_US/amy/medium/en_US-amy-medium.onnx")


def test_add_piper_voice_rejects_bad_sources(tmp_path, monkeypatch):
    service = _make_service(tmp_path, [], monkeypatch)
    calls = _stub_httpx(monkeypatch, b"data")
    bad_sources = [
        "",                                  # empty
        "https://example.com/voice.zip",    # not .onnx
        "ftp://example.com/a.onnx",         # not http(s)
        "../../etc/passwd",                 # path-shaped bare name
        "https://example.com/.hidden.onnx", # dotfile name via URL
    ]
    for src in bad_sources:
        with pytest.raises(ValueError):
            service.add_piper_voice(src)
    assert calls == []  # nothing hit the network
    assert list(service._piper_voice_dir().glob("*")) == []


def test_add_piper_voice_refuses_duplicate(tmp_path, monkeypatch):
    service = _make_service(tmp_path, ["en_US-existing-medium"], monkeypatch)
    calls = _stub_httpx(monkeypatch, b"data")
    with pytest.raises(ValueError, match="already cached"):
        service.add_piper_voice("en_US-existing-medium")
    assert calls == []


def test_add_piper_voice_http_error_leaves_no_partial_file(tmp_path, monkeypatch):
    service = _make_service(tmp_path, [], monkeypatch)
    _stub_httpx(monkeypatch, b"unwanted", status=500)
    with pytest.raises(ValueError, match="download failed"):
        service.add_piper_voice("https://example.com/a/en_US-gone.onnx")
    assert list(service._piper_voice_dir().glob("*")) == []


def test_add_piper_voice_sidecar_404_warns_but_keeps_voice(tmp_path, monkeypatch):
    # A mirror that serves .onnx but no .onnx.json: the voice must still be
    # kept (and listed) — with a warning, not a silent broken voice.
    service = _make_service(tmp_path, [], monkeypatch)
    _stub_httpx(monkeypatch, b"onnx-data",
                routes=[(".json", b"", 404)])
    res = service.add_piper_voice(
        "https://example.com/voices/en_US-nowarn-medium.onnx")
    assert res["name"] == "en_US-nowarn-medium"
    assert "warning" in res
    onnx = service._piper_voice_dir() / "en_US-nowarn-medium.onnx"
    assert onnx.read_bytes() == b"onnx-data"
    assert not onnx.with_name(onnx.name + ".json").exists()
    assert "en_US-nowarn-medium" in [
        v["name"] for v in service.list_piper_voices()]


def test_add_piper_voice_downloads_sidecar_from_link(tmp_path, monkeypatch):
    service = _make_service(tmp_path, [], monkeypatch)
    _stub_httpx(monkeypatch, b"",
                routes=[(".json", b'{"language": {"code": "en_US"}}', 200),
                        (".onnx", b"onnx-bytes", 200)])
    res = service.add_piper_voice(
        "https://mirror.example.com/voices/en_US-link-medium.onnx")
    assert "warning" not in res
    sidecar = service._piper_voice_dir() / "en_US-link-medium.onnx.json"
    assert b'"en_US"' in sidecar.read_bytes()


def test_add_piper_voice_empty_response_leaves_no_partial_file(tmp_path, monkeypatch):
    service = _make_service(tmp_path, [], monkeypatch)
    _stub_httpx(monkeypatch, b"", status=200)
    with pytest.raises(ValueError, match="no data"):
        service.add_piper_voice("https://example.com/a/en_US-empty.onnx")
    assert list(service._piper_voice_dir().glob("*")) == []


def test_add_piper_voice_enforces_size_limit(tmp_path, monkeypatch):
    import services.tts.tts_service as mod
    monkeypatch.setattr(mod, "_PIPER_VOICE_MAX_BYTES", 100)
    service = _make_service(tmp_path, [], monkeypatch)
    _stub_httpx(monkeypatch, b"x" * 1000)
    with pytest.raises(ValueError, match="too large"):
        service.add_piper_voice("https://example.com/a/en_US-huge.onnx")
    assert list(service._piper_voice_dir().glob("*")) == []


def test_route_voices_add_and_live_listing(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes.tts_routes import setup_tts_routes

    service = _make_service(tmp_path, ["en_US-a-medium"], monkeypatch)

    class _Stub:
        available = True
        def list_piper_voices(self):
            return service.list_piper_voices()
        def add_piper_voice(self, source):
            # Simulate a completed download landing in the live cache dir.
            (service._piper_voice_dir() / "en_US-new-medium.onnx").write_bytes(
                b"fake onnx")
            return {"name": "en_US-new-medium", "size_mb": 60.0}
        def synthesize(self, text, use_cache=True, voice=None):
            return b"RIFF"
        def synthesize_to_base64(self, text, voice=None):
            return "aW5kZXg="

    app = FastAPI()
    app.include_router(setup_tts_routes(_Stub()))
    client = TestClient(app)

    r = client.post("/api/tts/voices/add", json={"source": "en_US-new-medium"})
    assert r.status_code == 200
    assert r.json() == {"name": "en_US-new-medium", "size_mb": 60.0}

    # The live scan picks the new voice up immediately — no restart.
    r = client.get("/api/tts/voices")
    names = [v["name"] for v in r.json()["voices"]]
    assert names == ["en_US-a-medium", "en_US-new-medium"]

    # Bad source -> 400 with a user-facing message (no 500).
    class _BadStub(_Stub):
        def add_piper_voice(self, source):
            raise ValueError("the link must point to a .onnx file")

    app2 = FastAPI()
    app2.include_router(setup_tts_routes(_BadStub()))
    r = TestClient(app2).post("/api/tts/voices/add", json={"source": "junk"})
    assert r.status_code == 400
    assert r.json()["detail"]["message"] == "the link must point to a .onnx file"
