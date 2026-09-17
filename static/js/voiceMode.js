// static/js/voiceMode.js
// Voice Mode — hands-free dictation (Phase 2 of the voice-mode feature).
//
// While the user is in voice mode, mic audio is captured in an
// AudioWorklet (pcm16-processor.js: 16 kHz mono PCM16, 20 ms frames) and
// streamed over a WebSocket to /api/voice/stream. The server runs Silero
// VAD + the configured STT provider and sends back completed-utterance
// transcripts, which are appended to the chat composer (not sent).
//
// The LLM conversation stays on /api/chat_stream — this module only owns
// the audio edge: capture → WS → VAD → STT → composer.

import { showToast } from './ui.js';

class VoiceModeModule {
  constructor() {
    this.available = false;          // server says voice mode is usable
    this.sttProvider = 'disabled';
    this.autoSend = false;          // voice_auto_send setting (Phase 3)
    this.active = false;             // user turned voice mode on
    this.listening = false;          // ws open + streaming (UI pulse)
    this.transcribing = false;       // an utterance is in STT (UI state)
    this._ws = null;
    this._audioCtx = null;
    this._stream = null;
    this._worklet = null;
    this._pending = [];              // frames captured before ws open
    this._btn = document.getElementById('voice-mode-btn');
  }

  /* ── availability / UI wiring ── */

  async checkAvailability() {
    try {
      const res = await fetch('/api/voice/status', { credentials: 'same-origin' });
      if (!res.ok) throw new Error('status ' + res.status);
      const s = await res.json();
      this.available = !!(s.enabled && s.stt_available);
      this.sttProvider = s.stt_provider || 'disabled';
      this.autoSend = s.auto_send !== false;
      if (this._btn) {
        this._btn.style.display = this.available ? '' : 'none';
        this._btn.title = this.available
          ? 'Voice mode — ' + (this.autoSend ? 'what you say is sent to the assistant' : 'dictation into the composer')
          : 'Voice mode (disabled)';
      }
    } catch (e) {
      this.available = false;
      if (this._btn) this._btn.style.display = 'none';
    }
  }

  /* ── lifecycle ── */

  async start() {
    if (this.active) { this.stop(); return; }
    if (this._ws) { return; }  // already starting (ws not open yet)
    if (!window.isSecureContext) {
      showToast('Voice mode needs HTTPS (or localhost) for the microphone');
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showToast('Microphone not supported in this browser');
      return;
    }
    try {
      this._stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
    } catch (e) {
      if (e.name === 'NotAllowedError') showToast('Microphone access denied');
      else showToast('Microphone error: ' + e.message);
      return;
    }

    let ctx = null;
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      ctx = new AC();
      await ctx.audioWorklet.addModule('/static/js/pcm16-processor.js');
      const source = ctx.createMediaStreamSource(this._stream);
      const worklet = new AudioWorkletNode(ctx, 'pcm16-processor');
      source.connect(worklet);
      // Run the worklet without monitoring (no output to speakers).
      const sink = ctx.createGain();
      sink.gain.value = 0;
      worklet.connect(sink).connect(ctx.destination);
      worklet.port.onmessage = (ev) => this._onFrame(ev.data);
      this._audioCtx = ctx;
      this._worklet = worklet;

      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${location.host}/api/voice/stream`);
      ws.binaryType = 'arraybuffer';
      ws.onopen = () => {
        this._ws = ws;
        this.listening = this.active;
        this._updateBtn();
        // Flush frames captured while the socket was opening.
        for (const f of this._pending.splice(0)) ws.send(f);
      };
      ws.onmessage = (ev) => this._onMessage(ev.data);
      ws.onclose = (ev) => this._onClosed(ev);
      ws.onerror = () => { try { ws.close(); } catch (_) {} };

      this.active = true;
      this.listening = ws.readyState === WebSocket.OPEN;
      this._updateBtn();
      showToast('Voice mode on — just talk, it types for you');
    } catch (e) {
      console.error('Voice mode start failed:', e);
      this._teardown();
      showToast('Voice mode failed to start: ' + e.message);
    }
  }

  stop() {
    this._teardown();
    this.active = false;
    this._updateBtn();
  }

  _teardown() {
    this.active = false;
    this.listening = false;
    this.transcribing = false;
    this._pending = [];
    const ws = this._ws;
    this._ws = null;
    if (ws) { try { ws.onclose = null; ws.close(); } catch (_) {} }
    if (this._worklet) { try { this._worklet.disconnect(); } catch (_) {} this._worklet = null; }
    if (this._audioCtx) { try { this._audioCtx.close(); } catch (_) {} this._audioCtx = null; }
    if (this._stream) { this._stream.getTracks().forEach(t => t.stop()); this._stream = null; }
    this._updateBtn();
  }

  /* ── data flow ── */

  _onFrame(pcm16) {
    const ws = this._ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      if (this._pending.length < 100) this._pending.push(pcm16);  // ~2 s cap
      return;
    }
    try { ws.send(pcm16); } catch (_) {}
  }

  _onMessage(text) {
    let data;
    try { data = JSON.parse(text); } catch (_) { return; }
    if (data.status === 'ready') {
      this.listening = this.active;
      this._updateBtn();
    } else if (data.vad === 'start') {
      this.listening = true;
      this._updateBtn();
    } else if (data.stt === 'start') {
      this.transcribing = true;
      this._updateBtn();
    } else if (typeof data.transcript === 'string') {
      this.transcribing = false;
      this._updateBtn();
      if (data.transcript) this._onTranscript(data.transcript);
      // Empty transcript = the VAD segment was noise; stay quiet.
    } else if (data.error) {
      showToast('Voice mode: ' + data.error.message, 5000);
      this._teardown();
      return;
    }
  }

  _onClosed(ev) {
    if (!this.active) return;  // user-initiated stop
    const msg = { 4001: 'Voice mode is disabled in Settings',
                  4002: 'STT provider is not available',
                  4401: 'Not authenticated' }[ev.code];
    showToast('Voice mode stopped' + (msg ? ': ' + msg : ''), 4000);
    this._teardown();
  }

  _sid() {
    const m = window.sessionModule;
    return m && m.getCurrentSessionId ? m.getCurrentSessionId() : null;
  }

  _onTranscript(text) {
    // Phase 3 — the full loop. A completed utterance either barges in on a
    // spoken reply or is sent straight into the normal chat pipeline.
    const cm = window.chatModule;
    const tts = window.aiTTSManager;
    const busy = (sid) => !!(cm && cm.hasActiveStream && sid && cm.hasActiveStream(sid));
    if (tts && (tts.isPlaying || tts._processing)) {
      // Barge-in: the user spoke while the assistant was talking.
      tts.stop();
      if (busy(this._sid())) cm.abortCurrentRequest(true);  // Stop-button path
    }
    if (!this.autoSend || !cm || !cm.handleChatSubmit) {
      this._insertTranscript(text);
      return;
    }
    const input = document.getElementById('message');
    if (!input) { this._insertTranscript(text); return; }
    if (input.value.trim()) {
      // The user is typing — don't take the wheel, just append (Phase 2).
      this._insertTranscript(text);
      return;
    }
    if (busy(this._sid())) {
      // A turn is in flight (we just aborted it, or the stream outlived the
      // TTS): queue it — chat.js drains the queue the moment the stream ends.
      cm.send(text);
    } else {
      input.value = text;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      setTimeout(() => {
        cm.handleChatSubmit({ preventDefault() {} })
          .catch(err => console.error('voice auto-send failed', err));
      }, 0);
    }
  }

  _insertTranscript(text) {
    const input = document.getElementById('message');
    if (!input) return;
    const existing = input.value.trim();
    input.value = existing ? existing + ' ' + text : text;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
  }

  _updateBtn() {
    if (!this._btn) return;
    this._btn.classList.toggle('listening', this.active && this.listening);
    this._btn.classList.toggle('transcribing', this.transcribing);
    this._btn.setAttribute('aria-pressed', String(this.active));
    this._btn.title = this.active
      ? 'Voice mode ON — click to stop'
      : 'Voice mode — dictation into the composer';
  }
}

window.voiceModeModule = new VoiceModeModule();

// Wire the composer toggle (hidden until checkAvailability shows it).
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('voice-mode-btn');
  if (btn) btn.addEventListener('click', () => {
    if (window.voiceModeModule.active) window.voiceModeModule.stop();
    else window.voiceModeModule.start();
  });
  window.voiceModeModule.checkAvailability();
});

window.addEventListener('beforeunload', () => {
  if (window.voiceModeModule && window.voiceModeModule.active) {
    window.voiceModeModule._teardown();
  }
});
