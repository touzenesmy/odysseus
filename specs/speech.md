# Speech

Last updated: dev@3b6c1691 + fork voice-mode Phase 1-2 | 2026-09-16

## Scope

This spec covers speech behavior in:

- app service initialization and route registration in `app.py`;
- `services/stt/stt_service.py`;
- `services/tts/tts_service.py`;
- `services/vad/silero_vad.py`;
- `routes/stt_routes.py`;
- `routes/tts_routes.py`;
- `routes/voice_routes.py`;
- `src/upload_limits.py`;
- settings defaults/cache in `src/settings.py`;
- settings routes in `routes/auth_routes.py`;
- model endpoint cleanup in `routes/model_routes.py`;
- settings/tool aliases in `src/tool_implementations.py`;
- frontend modules `static/js/voiceRecorder.js`, `static/js/tts-ai.js`, `static/js/voiceMode.js`, `static/js/pcm16-processor.js`, `static/app.js`, `static/js/chat.js`, `static/js/slashCommands.js`, `static/js/keyboard-shortcuts.js`, `static/js/settings.js`, and `static/index.html`;
- optional dependency declarations in `requirements-optional.txt`;
- runtime cache path `data/tts_cache/`;
- tests covering speech service toggles, TTS speed/cache, STT temp cleanup, upload limits, settings scrubbing, model endpoint cleanup, and voice mode (VAD engine, WebSocket contract, decimator math).

## Current Call Sites Include

- chat mic/send button behavior;
- browser and server STT recording paths;
- chat message read-aloud buttons and streaming TTS queueing;
- `/tts` slash command playback;
- keyboard shortcut TTS activation;
- admin/settings API writes and `manage_settings` aliases;
- model endpoint deletion cleanup for `endpoint:<id>` speech providers.

## STT

`services.stt.STTService` owns speech-to-text provider behavior. `routes/stt_routes.py` owns `/api/stt/transcribe` and `/api/stt/stats`. `static/js/voiceRecorder.js` owns microphone capture, browser STT, server upload, and audio-attachment fallback.

Provider runtime:

- `disabled` returns unavailable and avoids provider calls;
- `browser` is client-side only through Web Speech API and does not call `/api/stt/transcribe`;
- `local` lazily imports `faster-whisper`, writes uploaded audio to a temporary WebM file, transcribes, and deletes the temp file in `finally`;
- `endpoint:<id>` resolves a `ModelEndpoint` and posts `audio.webm` to `/audio/transcriptions` with model and optional language.

Route behavior:

- audio uploads are capped by the shared STT upload limit from `src.upload_limits`, including environment override validation;
- empty uploads return a route error;
- uploaded content type, extension, and magic bytes are not strongly validated today;
- endpoint providers report optimistic availability and fail at request time if offline/misconfigured.

Frontend behavior:

- browser recording needs secure context and microphone permissions;
- server transcription success inserts text into the input;
- failed server transcription can attach the recorded audio file to chat instead; empty transcription shows a no-speech message.

## TTS

`services.tts.TTSService` owns text-to-speech provider behavior, speed parsing, cache behavior, and local/provider-specific synthesis. `routes/tts_routes.py` owns `/api/tts/stats`, `/api/tts/synthesize`, and cache clearing. `static/js/tts-ai.js` owns frontend playback, client object-URL caching, browser TTS, queueing, and streaming button state.

Provider runtime:

- `disabled` returns unavailable and avoids provider calls;
- `browser` is client-side only through `speechSynthesis`;
- `local` currently means Kokoro and requires `torch`, `kokoro`, `soundfile`, and CUDA/import availability;
- `piper` is the local CPU engine (`piper-tts` 1.8, C++/ONNX — no torch,
  works on Python 3.13+ where Kokoro cannot run). Voices are flat `*.onnx`
  files in `~/.cache/piper-voices` (override `ODYSSEUS_PIPER_VOICE_DIR`);
  voice names are sanitized (path-shaped or empty values are refused) and
  models lazy-load and cache per voice name. Availability is a file stat of
  the configured voice, not a model load. The voice's sidecar `.onnx.json`
  supplies display metadata (language/quality/sample rate) and is optional
  per voice (missing or malformed sidecars list the voice name-only).
  `tts_speed` maps to `SynthesisConfig.length_scale` (1.0x keeps the voice
  defaults; 2x halves it). `synthesize(text, voice=...)` and
  `synthesize_to_base64(text, voice=...)` accept a per-call voice override so
  the settings UI can audition a voice without writing settings.
- `endpoint:<id>` resolves a `ModelEndpoint` and posts to `/audio/speech`.
- unknown or non-string `tts_provider` values are treated as unavailable rather
  than being parsed as endpoint strings.

Route behavior:

- `/api/tts/synthesize` supports binary `audio` responses and JSON `base64` responses;
- `TTSRequest.voice` is an optional provider voice override, forwarded to
  synthesis (used for auditions);
- `GET /api/tts/voices` lists cached Piper voices (name plus display
  metadata) for the settings UI; it never loads models;
- binary responses choose WAV or MP3 MIME by audio magic bytes;
- synthesis input is passed to the service as submitted and capped there;
- malformed or nonpositive `tts_speed` falls back to `1.0`;
- provider unavailable returns 503; failed synthesis/transcription generally returns route-level failure.

## Voice Mode (hands-free dictation)

Voice mode is the hands-free dictation edge, added 2026-09-16 (fork, Phase 2 of the voice-mode feature). While the composer's voice-mode toggle is ON, `static/js/voiceMode.js` captures the mic through an AudioWorklet decimator (`static/js/pcm16-processor.js`, device rate → 16 kHz PCM16, fixed 20 ms frames) and streams it to `routes/voice_routes.py`. The server runs Silero v6 VAD (`services/vad/silero_vad.py`, model bundled inside `faster_whisper` assets — no extra download) and, per completed utterance, the configured STT provider; transcripts go back to the browser, which appends them to the chat composer. **The LLM conversation stays on `/api/chat_stream`** — this WebSocket is an audio edge, not a conversation engine: no session, history, or LLM state lives there. Phase 3 (auto-send + sentence-streamed TTS playback with barge-in) builds on this; until then transcripts are never sent automatically.

Endpoints (`routes/voice_routes.py`, registered in `app.py` with the shared `stt_service`):

- `WS /api/voice/stream` — the audio edge. Protocol: client sends binary PCM16 LE 16 kHz mono frames (any size; the server reslices into 32 ms VAD windows) and optional JSON control frames; the server sends `{"status":"ready"}` on connect, `{"vad":"start"}` / `{"stt":"start"}` state pulses, and `{"transcript":str,"stt_ms":int,"audio_ms":int,"reason":str}` per utterance, or `{"error":{"code","message"}}`. Close codes: 4401 unauthenticated, 4001 voice mode disabled, 4002 no STT provider available. STT runs off the event loop (`asyncio.to_thread`); a receive timeout (0.5 s) plus a 1 s quiet gap flushes any in-flight utterance instead of waiting for a silence tail that will never arrive (tab suspended, mic cut).
- `GET /api/voice/status` — the UI gate: `voice_mode_enabled`, STT availability/provider, and the current `vad_silence_ms`.

Auth: the app's HTTP `AuthMiddleware` is a `BaseHTTPMiddleware` and **cannot see WebSocket scopes**, so the WS handler validates the session cookie itself against `app.state.auth_manager` (the same cookie the middleware checks); auth-disabled deployments pass through.

VAD engine (`services/vad/silero_vad.py`): stateful Silero v6 wrapper (RNN `h`/`c` + 4 ms context), fed in exact 512-sample (32 ms) windows; `feed()` accepts arbitrary chunk sizes and returns events in order. State machine follows the Silero reference: a candidate end latches on the FIRST silence window and the utterance stops once `min_silence_ms` have elapsed since it; any speech window cancels the candidate. Defaults: 500 ms silence tail (conversational; the reference's 2000 ms is batch-oriented), 250 ms minimum utterance, 300 ms pre-roll kept via a 500 ms ring buffer, 60 s force-split. Blip-dropping measures **content** length (first speech window → end), not the pre-roll-inclusive buffer. `flush()` emits an in-flight utterance with `reason="flush"`; `detect_speech()` is the batch helper. Settings: `vad_silence_ms`, `vad_min_speech_ms` (thresholds are constants, not settings).

Settings (`src/settings.py`): `voice_mode_enabled` (default `false` — OFF means the WS refuses the connection and the composer toggle stays hidden; zero behavior change), `vad_silence_ms` (500), `vad_min_speech_ms` (250). The UI lives in the restored STT card in `static/index.html` (the STT settings card had been removed upstream and came back with voice mode): provider/model/language rows plus a Voice Mode section with the enable toggle, a microphone test (1.5 s level check), and the silence-to-stop slider. The composer toggle (`#voice-mode-btn`) appears only when `/api/voice/status` reports enabled + STT available.

Degraded behavior: missing `onnxruntime`/faster-whisper assets degrade the VAD (and with it voice mode) to unavailable rather than crashing the route; missing mic/secure context is handled client-side with toasts. On a shared-GPU box, a CUDA OOM while loading the Whisper model now falls back to CPU int8 (`services/stt/stt_service.py`) instead of leaving local STT dead.

Tests: `tests/test_voice_mode.py` (VAD engine on a real TTS-generated fixture in `tests/fixtures/voice_mode_speech.wav`: splitting, pre-roll, streaming-vs-batch, irregular frames, blips, pure silence, wav decodability; WS contract with a stub STT: gates, round-trip, gap-flush, silence-only, cookie auth; settings defaults + persistence round-trip; the CUDA→CPU fallback) plus node-based client checks under `tests/helpers/` (`check_client_js.mjs` loads `voiceMode.js` under a DOM shim; `check_pcm_processor.mjs` verifies the decimator's DC gain, 440 Hz pass, 10 kHz stopband, and frame cadence).

## Settings, Endpoints, And Cache

Speech providers are global settings under `data/settings.json`, with defaults in `src/settings.py`. Settings reads are scrubbed for non-admin callers, writes are admin-only, and `manage_settings` can change non-secret speech settings through aliases.

Visible UI state is not complete: backend and JS speech settings exist, and the STT settings JS exits when its removed DOM nodes are absent. Both speech settings cards were restored 2026-09-16 (they had been hidden/removed in the DOM). The TTS card shows Provider (disabled/browser/local/piper/endpoint), a Piper voice dropdown fed by `GET /api/tts/voices` with an Audition button (fixed sentence, voice override, no settings write), and the existing Preview button honors the selected Piper voice. The STT card (restored with voice mode) shows Provider/Model/Language plus the Voice Mode section (enable toggle, microphone test, silence-to-stop slider).

`routes.model_routes` clears `tts_provider` and `stt_provider` references when a referenced model endpoint is deleted.

TTS cache behavior:

- server cache lives under `data/tts_cache/`;
- cache keys include provider, model, voice, safe speed, and text;
- cache files are stored as MP3 or WAV;
- route stats expose global cache state;
- cache clear is global;
- frontend TTS has a separate object-URL cache.

`ODYSSEUS_TTS_CACHE_MAX_BYTES` bounds server cache growth and is forwarded by all Compose variants. The default is 500 MiB; invalid integers fall back to that default and values at or below zero disable eviction. After a cache write, enforcement scans only `.mp3`/`.wav`, ignores files that disappear or cannot be stated, and when over limit removes oldest-by-mtime entries toward 80% of the ceiling. Sort/stat/unlink failures are logged and do not fail synthesis.

## Security And Provenance

Speech routes rely on app-wide authentication and do not implement route-local admin or scope checks. Bearer-token callers that pass app auth can reach speech stats/synthesis/transcription/cache-clear surfaces using global speech settings.

Endpoint providers send user audio or assistant text to configured `ModelEndpoint` URLs with optional bearer keys. Endpoint lookup is by configured endpoint ID and currently does not enforce per-request owner filtering. `ModelEndpoint.api_key` is encrypted at rest and forwarded only process-side.

Microphone audio, uploaded audio, endpoint transcripts, and assistant text sent to TTS are untrusted/user/provider-visible data flows. Transcripts become user input; they are not trusted system instructions.

TTS cached audio can contain sensitive assistant text rendered as speech. The cache is global, has no owner partition or TTL, and is served inline/base64 by POST responses without a dedicated generated-file route.

## Degraded Behavior

- Optional local speech packages may be absent.
- Local STT can run CPU-only and tolerates missing/broken torch by falling back to CPU/int8 behavior.
- Local TTS/Kokoro extras are declared as `kokoro==0.9.4` plus `soundfile` only for Python 3.11-3.12; Python 3.13+ intentionally skips them because Kokoro excludes those runtimes. Even where installed, local Kokoro remains unavailable without a CUDA-capable torch build/GPU.
- Piper extras (`piper-tts`, `onnxruntime`) are optional with no version pin and work on all supported runtimes including 3.13+; a missing voice file or missing package degrades to `available: false` (piper) or a per-request synthesis failure, not a crash.
- External endpoint providers can be offline or misconfigured and may only fail at request time.
- Browser `speechSynthesis`, `SpeechRecognition`, `webkitSpeechRecognition`, secure context, and microphone permissions can be absent.
- Docker GPU overlays are passthrough-only and do not install speech engines by themselves.
- Optional dependency errors and route error wording are not fully consistent across STT and TTS.

## Testing Coverage

Existing coverage includes speech service toggles, malformed/non-string TTS provider and speed handling, cache stats plus configured eviction/disable/file filtering/error handling, STT temp cleanup, direct upload limits, model routes, settings scrubbing, and the Piper provider (tests/test_tts_piper_provider.py: availability, voice-name sanitization, voice listing with/without sidecars, synthesis + cache keys + speed mapping, `/api/tts/voices` and the voice-override route contract). Voice mode is covered by tests/test_voice_mode.py (VAD engine, WebSocket contract incl. gap-flush and cookie auth, settings persistence, CUDA→CPU fallback) and node decimator checks under tests/helpers/.

Missing coverage includes route-level STT/TTS success and failure shapes, auth/API-token behavior, endpoint owner isolation, STT type/magic rejection, TTS request-size/no-store/cache privacy behavior, degraded optional dependency paths, and frontend recorder/TTS fallback states.

## Current Gaps

- Visible speech settings UI is incomplete relative to backend settings.
- Speech routes need a deliberate API-token/scope policy.
- Endpoint speech providers need owner-isolation or explicit global-settings documentation.
- TTS cache needs privacy policy: owner partition, TTL, no-store response headers, or accepted global cache semantics.
- STT upload validation needs content type/extension/magic-byte policy.
- Browser/compare STT mic behavior needs a product decision or regression test because compare can force send-button visuals while shared empty-input logic can start recording.
