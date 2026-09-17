# services/vad/silero_vad.py
"""Streaming Silero VAD over a 16 kHz PCM stream (CPU, ONNX).

Wraps the Silero v6 ONNX model that ships inside faster-whisper
(``faster_whisper/assets/silero_vad_v6.onnx``), so there is no extra
model download. The model is stateful (RNN ``h``/``c`` + a 4 ms input
context), so each stream gets its own ``SileroVAD`` instance fed in
exact 512-sample (32 ms) windows.

Two consumers:
  * the voice WebSocket (``routes/voice_routes.py``) — ``feed`` per
    20 ms client frame, read the returned start/stop events;
  * batch callers — ``detect_speech`` over a full buffer.

The state machine follows the Silero reference implementation
(snakers4/silero-vad ``vad.py``): a candidate end point latches on the
FIRST silence window and the utterance stops once ``min_silence_ms``
have elapsed since it; any window above ``threshold`` cancels the
candidate. Conversational-tuned defaults: 500 ms silence tail (the
reference's 2000 ms is batch-oriented) and a 250 ms minimum utterance.
"""

import io
import logging
import threading
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
WINDOW_SAMPLES = 512  # 32 ms — the Silero window size (fixed by the model)
MAX_UTTERANCE_SAMPLES = 60 * SAMPLE_RATE  # hard 60 s cap per utterance
RING_CAP_BYTES = int(0.5 * SAMPLE_RATE) * 2  # 500 ms pre-roll ring

_DEFAULT_MODEL_PATH: Optional[str] = None
_MODEL_PATH_LOCK = threading.Lock()


def _model_path() -> Path:
    global _DEFAULT_MODEL_PATH
    with _MODEL_PATH_LOCK:
        if _DEFAULT_MODEL_PATH:
            return Path(_DEFAULT_MODEL_PATH)
        import os
        override = os.environ.get("ODYSSEUS_SILERO_VAD_PATH")
        if override:
            _DEFAULT_MODEL_PATH = override
            return Path(override)
        try:
            # faster-whisper bundles the model — zero extra download.
            from faster_whisper.utils import get_assets_path
            path = Path(get_assets_path()) / "silero_vad_v6.onnx"
        except Exception:
            # faster-whisper not installed — fall back to the user cache
            # (mirrors the Piper voice-dir convention).
            path = Path.home() / ".cache" / "odysseus" / "silero_vad_v6.onnx"
        _DEFAULT_MODEL_PATH = str(path)
        return path


def _load_session(model_path: Optional[Path] = None):
    """Load a fresh ONNX session (and verify it runs one window)."""
    import onnxruntime
    path = model_path or _model_path()
    opts = onnxruntime.SessionOptions()
    opts.inter_op_num_threads = 1
    opts.intra_op_num_threads = 1
    opts.enable_cpu_mem_arena = False
    opts.log_severity_level = 4
    session = onnxruntime.InferenceSession(str(path),
                                           providers=["CPUExecutionProvider"],
                                           sess_options=opts)
    out = session.run(
        None,
        {
            "input": np.zeros((1, 64 + WINDOW_SAMPLES), dtype=np.float32),
            "h": np.zeros((1, 1, 128), dtype=np.float32),
            "c": np.zeros((1, 1, 128), dtype=np.float32),
        },
    )
    assert out[0].size == 1
    return session


@dataclass
class VadConfig:
    threshold: float = 0.5  # prob >= t: speech
    neg_threshold: float = 0.35  # prob < nt: definitely silence
    min_speech_ms: int = 250  # drop utterances shorter than this
    min_silence_ms: int = 500  # silence tail that ends an utterance
    max_speech_s: float = 60.0  # force-split very long speech
    speech_pad_ms: int = 300  # pre-roll kept before an utterance

    def __post_init__(self):
        if self.min_silence_ms < 50:
            self.min_silence_ms = 50
        if self.min_speech_ms < 0:
            self.min_speech_ms = 0  # negative would let blips through



class SileroVAD:
    """Stateful speech detector for one audio stream.

    ``feed`` accepts any number of 16-bit PCM samples (it reslices into
    512-sample windows internally) and returns VAD events in feed order:

      {"event": "start", "t_s": float}
      {"event": "stop", "t_s": float, "audio": bytes, "duration_s": float,
       "reason": str}

    ``audio`` is the utterance as a 16-bit PCM16 LE mono 16 kHz WAV with
    up to ``speech_pad_ms`` of pre-roll — ready for
    ``STTService.transcribe``.
    """

    def __init__(self, config: Optional[VadConfig] = None,
                 model_path: Optional[Path] = None):
        self.cfg = config or VadConfig()
        self._session = _load_session(model_path)
        # RNN state + 4 ms input context (per the Silero call signature).
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)
        # Pre-roll ring: recent raw audio as (stream_index, bytes) chunks,
        # capped at RING_CAP_BYTES, so an utterance can be seeded with up to
        # speech_pad_ms of the audio before the trigger window — accurately,
        # regardless of feed chunk size (batch or 20 ms frames).
        self._ring: list = []  # [(start_index, pcm16_bytes), ...]

        # Detector state (stream-absolute sample indices)
        self._in_speech = False
        self._speech_start = 0  # first content sample (incl. pre-roll)
        self._trigger_idx = 0  # first window above threshold (content start)
        self._temp_end = 0  # latched candidate-end window (0 = none)
        self._force_split_at = 0
        self._total_windows = 0
        self._carry = bytearray()  # partial 512-sample window
        self._feed_start = 0
        self._feed_pcm = b""
        self._n = 0
        # Utterance buffer (raw PCM16 bytes from the pre-roll start).
        self._buf = bytearray()
        self._buf_start_idx = 0  # stream index of _buf[0]
        self._buf_end_idx = 0    # stream index just past _buf[-1]
        self._buf_full = False

    # ── model ──

    def _prob(self, window: np.ndarray) -> float:
        w = window.reshape(1, -1)
        audio = np.concatenate([self._context, w], axis=1)
        out, self._h, self._c = self._session.run(
            None, {"input": audio, "h": self._h, "c": self._c})
        self._context = w[:, -64:]
        return float(out.reshape(-1)[0])

    def _ring_slice(self, lo: int, hi: int) -> bytes:
        """Ring audio in [lo, hi) samples (empty if the ring can't cover)."""
        out = []
        for off, b in self._ring:
            b_lo = max(0, lo - off) * 2
            b_hi = min(len(b), hi - off) * 2
            if b_hi > b_lo:
                out.append(b[b_lo:b_hi])
        return b"".join(out)

    # ── public API ──

    def feed(self, pcm16: bytes) -> list:
        """Feed raw PCM16 LE mono 16 kHz audio; returns VAD events."""
        n = len(pcm16) // 2
        if n == 0:
            return []
        # Stream index of the first sample of THIS feed call (== _feed_start,
        # computed below before any window is cut).
        self._feed_start = len(self._carry) // 2 + self._total_windows * WINDOW_SAMPLES
        self._ring.append((self._feed_start, pcm16))
        total = sum(len(b) for _, b in self._ring)
        if total > RING_CAP_BYTES:
            # Trim oldest: pop whole small chunks, and if the oldest chunk
            # alone exceeds the cap, keep only its tail.
            while total > RING_CAP_BYTES and self._ring:
                off, b = self._ring[0]
                if len(b) <= total - RING_CAP_BYTES:
                    self._ring.pop(0)
                    total -= len(b)
                else:
                    keep = len(b) - (total - RING_CAP_BYTES)
                    self._ring[0] = (off + keep // 2, b[keep:])
                    total = RING_CAP_BYTES
                    break

        events = []
        self._feed_pcm = pcm16
        self._n = n
        self._carry.extend(pcm16)
        while len(self._carry) >= WINDOW_SAMPLES * 2:
            window = np.frombuffer(self._carry[: WINDOW_SAMPLES * 2],
                                   dtype=np.int16).astype(np.float32)
            del self._carry[: WINDOW_SAMPLES * 2]
            idx = self._total_windows * WINDOW_SAMPLES
            # Keep the utterance buffer current up to this window so a
            # stop triggered by it can cut audio that was already fed.
            self._extend_to(idx)
            events.extend(self._process_window(idx, self._prob(window)))
            self._total_windows += 1
        return events

    def _extend_to(self, idx: int):
        """Extend the utterance buffer with fed audio up to sample ``idx``.

        The buffer lags the stream by one window (the 512-sample window
        being scored was cut from an earlier feed), so [buf_end,
        feed_start) was fed by an EARLIER feed call — recover it from the
        pre-roll ring (500 ms cap ≫ the 64 ms max lag, so coverage is
        guaranteed). Slicing that range out of THIS feed's PCM would splice
        audio from up to 64 ms in the future into every utterance: the
        browser streams 640-sample frames, shorter than the 512-sample
        window, so each feed's tail is already part of the next window.
        """
        if not self._in_speech or self._buf_full:
            return
        end = min(idx, self._feed_start + self._n)
        if end <= self._buf_end_idx:
            return
        gap_end = min(end, self._feed_start)
        if gap_end > self._buf_end_idx:
            self._buf.extend(self._ring_slice(self._buf_end_idx, gap_end))
            self._buf_end_idx = gap_end
        src = self._buf_end_idx - self._feed_start
        if src < 0:
            src = 0
        need = end - self._buf_end_idx
        take = min(self._n - src, need)
        self._buf.extend(self._feed_pcm[src * 2: src * 2 + take * 2])
        self._buf_end_idx = self._buf_end_idx + take
        if len(self._buf) > MAX_UTTERANCE_SAMPLES * 2:
            del self._buf[MAX_UTTERANCE_SAMPLES * 2:]
            self._buf_full = True

    # ── state machine (one 32 ms window) ──

    def _process_window(self, idx: int, prob: float) -> list:
        cfg = self.cfg
        if not self._in_speech:
            if prob >= cfg.threshold:
                pad = min(int(cfg.speech_pad_ms / 1000 * SAMPLE_RATE), idx)
                self._in_speech = True
                self._speech_start = max(0, idx - pad)
                self._trigger_idx = idx
                self._buf = bytearray(self._ring_slice(idx - pad, idx))
                self._buf_start_idx = max(0, idx - pad)
                self._buf_end_idx = idx
                self._temp_end = 0
                self._force_split_at = (
                    idx + int(cfg.max_speech_s * SAMPLE_RATE))
                return [{"event": "start",
                         "t_s": self._speech_start / SAMPLE_RATE}]
            return []

        # In speech: latch a candidate end on the first silence window,
        # cancel it on real speech, stop once the tail has run out.
        if prob >= cfg.threshold:
            self._temp_end = 0
        elif self._temp_end == 0:
            self._temp_end = idx
        elif idx - self._temp_end >= int(cfg.min_silence_ms / 1000
                                        * SAMPLE_RATE):
            return self._stop(self._temp_end, idx, "silence")
        if idx >= self._force_split_at:
            return self._stop(self._force_split_at, idx, "max_duration")
        return []

    def _stop(self, end_idx: int, stop_idx: int, reason: str) -> list:
        """Cut the current utterance at ``end_idx`` (content end)."""
        cfg = self.cfg
        end_idx = min(end_idx, self._buf_end_idx)
        pcm = bytes(self._buf[: max(0, (end_idx - self._buf_start_idx) * 2)])
        duration_s = len(pcm) // 2 / SAMPLE_RATE
        # Blip check on CONTENT length (trigger → end), not the buffered
        # length: the buffer carries up to speech_pad_ms of pre-roll.
        content_s = max(0.0, (end_idx - self._trigger_idx) / SAMPLE_RATE)
        self._in_speech = False
        self._buf = bytearray()
        self._buf_full = False
        self._temp_end = 0
        if content_s < cfg.min_speech_ms / 1000:
            return []  # blip — drop
        return [{
            "event": "stop",
            "t_s": stop_idx / SAMPLE_RATE,
            "audio": self._wav(pcm),
            "duration_s": duration_s,
            "reason": reason,
        }]

    def flush(self) -> list:
        """End-of-stream: emit any in-flight utterance (reason="flush")."""
        if self._in_speech:
            total = self._total_windows * WINDOW_SAMPLES
            return self._stop(total, total, "flush")
        return []

    # ── helpers ──

    @staticmethod
    def _wav(pcm: bytes) -> bytes:
        bio = io.BytesIO()
        out = wave.open(bio, "wb")
        try:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(SAMPLE_RATE)
            out.writeframes(pcm)
        finally:
            out.close()
        return bio.getvalue()


# ── Batch helper ──

def detect_speech(pcm16: bytes, config: Optional[VadConfig] = None,
                  model_path: Optional[Path] = None):
    """Batch VAD over a full PCM16 LE mono 16 kHz buffer.

    Returns a list of {"start": s, "end": e, "audio": wav_bytes} speech
    segments (``start``/``end`` in seconds), skipping segments shorter
    than ``min_speech_ms``.
    """
    vad = SileroVAD(config, model_path)
    segments = []
    start = None
    for ev in vad.feed(pcm16) + vad.flush():
        if ev["event"] == "start":
            start = ev["t_s"]
        elif ev["event"] == "stop" and start is not None:
            segments.append({"start": start, "end": ev["t_s"],
                             "audio": ev["audio"]})
            start = None
    return segments
