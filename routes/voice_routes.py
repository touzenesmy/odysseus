# routes/voice_routes.py
"""Voice mode WebSocket — the audio edge for hands-free dictation.

Phase 2 of the voice-mode feature (see specs/speech.md, "Voice mode"
section): while the browser's voice-mode toggle is ON it streams 16 kHz
mono PCM16 frames here; the server runs Silero VAD + the configured STT
provider and sends completed utterances back as transcripts. The client
inserts them into the composer — the LLM conversation stays on
``/api/chat_stream``. This WS is an *audio edge*, not a conversation
engine: no session, history, or LLM state lives here.

Protocol (WS ``/api/voice/stream``):
  client → server
    binary            PCM16 LE, 16 kHz, mono (20 ms / 640-sample frames;
                      any size is tolerated — the server reslices)
  server → client
    text JSON        {"status": "ready", ...}    on connect (after gates)
                     {"vad": "start"}           VAD pulse for the UI
                     {"transcript": str,
                      "stt_ms": int, "audio_ms": int}
                     {"error": {"code": str, "message": str}}

Auth: WebSockets bypass the HTTP AuthMiddleware (Starlette
BaseHTTPMiddleware only sees HTTP scopes), so the handler checks the
session cookie itself — the same cookie the middleware validates.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket

logger = logging.getLogger(__name__)


def setup_voice_routes(stt_service):
    router = APIRouter(prefix="/api/voice", tags=["voice"])

    @router.get("/status")
    async def voice_status():
        """UI gate: is voice mode usable right now? (no auth beyond the
        normal HTTP middleware — mirrors the other /api/* read routes)."""
        # Settings-only on purpose: STTService.get_stats() touches the model
        # (available → lazy WhisperModel load = seconds of event-loop
        # blocking on every page load). The real availability check
        # happens at WS connect, off the loop.
        from src.settings import load_settings
        settings = load_settings()
        provider = settings.get("stt_provider", "disabled")
        return {
            "enabled": bool(settings.get("voice_mode_enabled")),
            "stt_available": bool(settings.get("stt_enabled"))
            and _provider_usable(settings),
            "stt_provider": provider,
            "vad_silence_ms": _int_setting("vad_silence_ms", 500),
            "vad_threshold": _float_setting("vad_threshold", 0.5),
            "auto_send": bool(settings.get("voice_auto_send", True)),
        }

    @router.websocket("/stream")
    async def voice_stream(ws: WebSocket):
        await ws.accept()
        try:
            if not _ws_authenticated(ws):
                await ws.close(code=4401)
                return

            from src.settings import load_settings
            settings = load_settings()
            if not settings.get("voice_mode_enabled"):
                await _send(ws, {"error": {"code": "voice_mode_disabled",
                                           "message": "Voice mode is not enabled in Settings."}})
                await ws.close(code=4001)
                return

            if not _provider_usable(settings):
                await _send(ws, {"error": {"code": "stt_unavailable",
                                           "message": "Enable a server STT provider (local Whisper) in Settings → Voice Mode."}})
                await ws.close(code=4002)
                return

            # Off the event loop: for 'local' this warms the Whisper model
            # (a one-time multi-second load) before the first utterance.
            stt_ok = await asyncio.to_thread(lambda: bool(stt_service.available))
            if not stt_ok:
                await _send(ws, {"error": {"code": "stt_unavailable",
                                           "message": "STT provider is not available (model failed to load)."}})
                await ws.close(code=4002)
                return

            from services.vad.silero_vad import SileroVAD, VadConfig, SAMPLE_RATE
            vad = SileroVAD(VadConfig(
                threshold=_float_setting("vad_threshold", 0.5),
                min_silence_ms=_int_setting("vad_silence_ms", 500),
                min_speech_ms=_int_setting("vad_min_speech_ms", 250),
            ))
            await _send(ws, {
                "status": "ready",
                "sample_rate": SAMPLE_RATE,
                "frame_samples": 640,
            })
            logger.info("Voice mode stream opened (VAD + %s STT)",
                        stt_service.get_stats().get("provider"))

            import time
            # The client normally streams continuously (silence frames
            # included), so a gap of FLUSH_AFTER_S with no frames means the
            # stream itself stopped (tab suspended, mic cut) — flush any
            # in-flight utterance instead of waiting for a silence tail
            # that will never arrive.
            FLUSH_AFTER_S = 2.0
            last_audio = time.monotonic()

            async def emit(events):
                for ev in events:
                    if ev["event"] == "start":
                        await _send(ws, {"vad": "start"})
                        continue
                    # "stop": transcribe the utterance off the event loop
                    # (local Whisper is a CPU burst of ~1–2 s).
                    await _send(ws, {"stt": "start"})
                    t0 = time.monotonic()
                    text = await asyncio.to_thread(
                        stt_service.transcribe, ev["audio"])
                    stt_ms = int((time.monotonic() - t0) * 1000)
                    if not text:
                        logger.info("Voice mode: VAD utterance produced no transcript (%.1f s audio)",
                                    ev["duration_s"])
                    await _send(ws, {
                        "transcript": text or "",
                        "stt_ms": stt_ms,
                        "audio_ms": int(ev["duration_s"] * 1000),
                        "reason": ev.get("reason"),
                    })
                    logger.info("Voice mode transcript: %.1f s audio → %d ms STT, %r",
                                ev["duration_s"], stt_ms, (text or "")[:80])

            while True:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=0.5)
                except asyncio.TimeoutError:
                    if time.monotonic() - last_audio >= FLUSH_AFTER_S:
                        await emit(vad.flush())
                    continue
                if msg.get("type") == "websocket.disconnect":
                    return
                pcm = msg.get("bytes")
                if pcm:
                    last_audio = time.monotonic()
                    await emit(vad.feed(pcm))
        except Exception as e:
            logger.debug("Voice mode stream ended: %s", e)
        finally:
            try:
                await ws.close()
            except Exception:
                pass

    return router


def _int_setting(name: str, default: int) -> int:
    """Numeric setting, clamped (bad settings.json values can't stall the VAD)."""
    from src.settings import get_setting
    try:
        return int(get_setting(name, default))
    except (TypeError, ValueError):
        return default


def _float_setting(name: str, default: float) -> float:
    """Float setting, clamped to [0.05, 0.95] (same contract as _int_setting)."""
    from src.settings import get_setting
    try:
        return max(0.05, min(0.95, float(get_setting(name, default))))
    except (TypeError, ValueError):
        return default


def _provider_usable(settings: dict) -> bool:
    """Voice mode needs a server-side STT provider (browser runs client-side)."""
    return settings.get("stt_provider") in ("local",) or str(
        settings.get("stt_provider", "")).startswith("endpoint:")


def _ws_authenticated(ws: WebSocket) -> bool:
    """Cookie-session auth for the WS (the HTTP middleware can't see it)."""
    from src.owner_identity import auth_disabled
    if auth_disabled():
        return True
    manager = getattr(ws.app.state, "auth_manager", None)
    if manager is None:
        # No auth infrastructure attached (bare test apps). The real app
        # always sets app.state.auth_manager (app.py), so this path is
        # test-only.
        return True
    from routes.auth_routes import SESSION_COOKIE
    token = ws.cookies.get(SESSION_COOKIE)
    try:
        return bool(token) and manager.validate_token(token)
    except Exception:
        return False


async def _send(ws: WebSocket, payload: dict):
    try:
        await ws.send_text(json.dumps(payload))
    except Exception:
        pass  # client gone — the receive loop will exit


# Module-level helper so tests can build a standalone app.
def create_voice_app(stt_service):
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(setup_voice_routes(stt_service))
    return app
