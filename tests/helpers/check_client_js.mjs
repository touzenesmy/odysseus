// tests/helpers/check_client_js.mjs
// Loads the voice-mode client modules under a minimal DOM shim and asserts
// they construct and wire without throwing. Run: node tests/helpers/check_client_js.mjs

import { readFileSync } from 'node:fs';

// ── DOM shim ──
const listeners = {};
const elMap = {};
function makeEl(id) {
  let _html = '';
  return {
    id, style: {}, dataset: {},
    value: '', title: '',
    set innerHTML(v) { _html = String(v); },
    get innerHTML() { return _html; },
    get textContent() { return _html.replace(/<[^>]*>/g, ''); },
    get innerText() { return this.textContent; },
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    setAttribute() {}, getAttribute() { return null; },
    addEventListener(type, fn) { (listeners[id + ':' + type] ||= []).push(fn); },
    dispatchEvent() {}, focus() {},
    querySelectorAll() { return []; },
  };
}
globalThis.document = {
  getElementById: (id) => (elMap[id] ||= makeEl(id)),
  createElement: () => makeEl('dyn'),
  addEventListener() {},
};
globalThis.window = globalThis;
globalThis.location = { protocol: 'http:', host: 'localhost:8000' };
globalThis.fetch = async () => { throw new Error('no fetch in shim'); };
globalThis.WebSocket = class { readyState = 0; };
class FakeAudioNode {
  constructor() { this.port = { postMessage() {} }; this.gain = { value: 0 }; }
  connect() { return this; }
  disconnect() {}
}
globalThis.AudioWorkletNode = class FakeAW extends FakeAudioNode {};
globalThis.AudioContext = class {
  constructor() {
    this.audioWorklet = { addModule: async () => {} };
    this.destination = {};
  }
  createMediaStreamSource() { return new FakeAudioNode(); }
  createGain() { return new FakeAudioNode(); }
  close() {}
};
globalThis.isSecureContext = false;
globalThis.addEventListener = () => {}; // window shim (voiceMode.js binds beforeunload)

// Load voiceMode.js source and execute it in this scope (it's an ES module
// that imports ./ui.js — we stub that import by pre-populating a module map
// is not possible in plain node, so instead we exec the source after
// transforming the single import into a no-op).
let src = readFileSync(new URL('../../static/js/voiceMode.js', import.meta.url), 'utf8');
src = src.replace(/import\s*\{[^}]*\}\s*from\s*'\.\/ui\.js';/,
                  'const showToast = (m) => globalThis.__lastToast = m;');
const mod = await import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'));
if (!globalThis.voiceModeModule) throw new Error('voiceModeModule not registered');
console.log('voiceMode module loaded, available =', globalThis.voiceModeModule.available);
console.log('voiceMode OK');

// ── Phase 3 behavior: _onTranscript routing (the full-loop decision) ──
const vm = globalThis.voiceModeModule;
const input = document.getElementById('message');
const events = [];
let ttsStopped = 0;
const state = { busy: false, ttsPlaying: false, processing: false };
globalThis.sessionModule = { getCurrentSessionId: () => 's1' };
globalThis.aiTTSManager = {
  get isPlaying() { return state.ttsPlaying; },
  get _processing() { return state.processing; },
  stop() { ttsStopped++; state.ttsPlaying = false; state.processing = false; },
};
globalThis.chatModule = {
  hasActiveStream: (sid) => state.busy,
  send: (t) => { events.push(['send', t]); },
  abortCurrentRequest: (x) => { events.push(['abort', x]); },
  handleChatSubmit: async () => { events.push(['submit', input.value]); input.value = ''; },
};
const tick = () => new Promise(r => setTimeout(r, 20));
const ev = (a, b) => events.some(x => x[0] === a && x[1] === b);

// 1. idle + auto-send ON → transcript goes through the normal submit path
vm.autoSend = true;
vm._onTranscript('hello there');
await tick();
if (!ev('submit', 'hello there')) throw new Error('auto-send did not submit: ' + JSON.stringify(events));

// 2. Barge-in fires at VAD speech onset (before the transcript arrives):
//    stop TTS + abort the run — the assistant goes silent instantly.
events.length = 0; ttsStopped = 0; state.busy = true; state.ttsPlaying = true;
vm._onMessage(JSON.stringify({ vad: 'start' }));
if (ttsStopped !== 1 || !ev('abort', true))
  throw new Error('onset barge-in wrong: ' + JSON.stringify({ ttsStopped, events }));

// 2b. The transcript arrives after the onset (VAD tail + STT) → just queue.
// (Phase 3.7: a barge-in transcript during TTS must be substantive — ≤2 words
// in that window are the echo class, dropped by the gate in _onTranscript.)
events.length = 0; ttsStopped = 0;
vm._onTranscript('stop talking, check the logs');
if (ttsStopped !== 0 || !ev('send', 'stop talking, check the logs'))
  throw new Error('barge-in queue wrong: ' + JSON.stringify({ ttsStopped, events }));

// 3. busy, TTS idle → just queue (drained when the stream ends)
events.length = 0; state.ttsPlaying = false;
vm._onTranscript('next question');
if (!ev('send', 'next question')) throw new Error('busy queue wrong: ' + JSON.stringify(events));

// 4. auto-send OFF → composer insert only
events.length = 0; state.busy = false; vm.autoSend = false;
vm._onTranscript('typed mode');
await tick();
if (input.value !== 'typed mode' || events.length !== 0)
  throw new Error('insert-only wrong: ' + JSON.stringify({ v: input.value, events }));

// 5. composer not empty → append, never steal the user's text
events.length = 0; vm.autoSend = true; input.value = 'my draft ';
vm._onTranscript('appended');
await tick();
if (input.value !== 'my draft appended' || events.length !== 0)
  throw new Error('append wrong: ' + JSON.stringify({ v: input.value, events }));

console.log('voiceMode phase3 OK');

// ── Phase 3.7: echo gate — a transcript that STARTED while the assistant's
// TTS was audible is the mic hearing the assistant's own voice. Short ones
// (empty / a mangled word or two) are dropped; substantive barge-ins are kept.
{
  const vm = globalThis.voiceModeModule;
  vm.autoSend = true;

  // (1) onset DURING TTS → 1-word echo transcript is dropped (never inserted/sent)
  input.value = ''; events.length = 0;
  state.busy = true; state.ttsPlaying = true; state.processing = true;
  vm._onMessage(JSON.stringify({ vad: 'start' }));   // barge-in: abort + TTS stop
  const aborted = events.some(e => e[0] === 'abort' && e[1] === true);
  vm._onTranscript('You');
  if (input.value !== '')
    throw new Error('echo inserted into composer: ' + JSON.stringify(input.value));
  if (events.some(e => e[0] === 'send' || e[0] === 'submit'))
    throw new Error('echo auto-sent: ' + JSON.stringify(events));
  if (!aborted) throw new Error('barge-in abort lost by echo gate');

  // (1b) An EMPTY transcript (noise — the dominant echo class: 7 of 40 in
  // the live journal) must ALSO consume the flag. If it doesn't, the flag
  // leaks to the next real utterance and a short real barge-in right after
  // an echo gets dropped (the pre-fix behavior).
  input.value = ''; events.length = 0;
  state.busy = true; state.ttsPlaying = true; state.processing = true;
  vm._onMessage(JSON.stringify({ vad: 'start' }));   // echo onset → barge-in stops TTS
  vm._onMessage(JSON.stringify({ transcript: '' }));  // empty echo must consume the flag
  state.busy = false; state.ttsPlaying = false; state.processing = false;
  vm._onMessage(JSON.stringify({ vad: 'start' }));   // real onset, TTS idle
  vm._onMessage(JSON.stringify({ transcript: 'stop' }));
  await tick();
  if (!ev('submit', 'stop'))
    throw new Error('short barge-in after an empty echo dropped: ' + JSON.stringify({ v: input.value, events }));

  // (2) onset DURING TTS → multi-word barge-in is KEPT (queued while busy)
  input.value = ''; events.length = 0;
  state.busy = true; state.ttsPlaying = true; state.processing = true;
  vm._onMessage(JSON.stringify({ vad: 'start' }));
  vm._onTranscript('stop that and check the logs instead');
  if (!ev('send', 'stop that and check the logs instead'))
    throw new Error('multi-word barge-in dropped: ' + JSON.stringify(events));

  // (3) onset while TTS IDLE → short transcript is a real user, kept
  input.value = ''; events.length = 0;
  state.busy = false; state.ttsPlaying = false; state.processing = false;
  vm._onMessage(JSON.stringify({ vad: 'start' }));
  vm._onTranscript('Thank you.');
  await tick();
  if (!ev('submit', 'Thank you.'))
    throw new Error('idle short transcript dropped: ' + JSON.stringify({ v: input.value, events }));
  console.log('voiceMode echo-gate OK');
}


// ── TTS: extractPlainText must never hand thinking to the synthesizer ──
let ttsSrc = readFileSync(new URL('../../static/js/tts-ai.js', import.meta.url), 'utf8');
ttsSrc = ttsSrc.replace(/import\s*\{[^}]*\}\s*from\s*'\.\/appConfig\.js';/,
                        'const getSettings = async () => ({ tts_enabled: true });');
const ttsMod = await import('data:text/javascript;base64,' + Buffer.from(ttsSrc).toString('base64'));
const mgr = new ttsMod.AITTSManager();

// closed thinking block: reasoning stripped, reply kept
let t1 = mgr.extractPlainText('<thinking>I should verify this carefully. </thinking>Here is the answer: 42');
if (!t1.includes('answer: 42') || t1.includes('I should verify'))
  throw new Error('closed thinking leak: ' + JSON.stringify(t1));

// malformed stream (never closed): everything after the tag is reasoning
let t2 = mgr.extractPlainText('Sure! <thinking>Let me reason about this step by step. The answer should be 7.');
if (t2 !== 'Sure!')
  throw new Error('unclosed thinking leak: ' + JSON.stringify(t2));

// reply after a closed block, plus markdown
let t3 = mgr.extractPlainText('<thinking>working through it...</thinking>**Done** — it works.');
if (!t3.includes('Done') || t3.includes('thinking...'))
  throw new Error('mixed strip wrong: ' + JSON.stringify(t3));

// the app rewrites the tag to <think time="12.3"> when thinking finalizes —
// the bare-tag strip let that block (reasoning included) reach the synthesizer
let t4 = mgr.extractPlainText('<think time="12.3">I need to figure out the answer carefully.</think>All good.');
if (t4 !== 'All good.')
  throw new Error('time-attributed thinking leak: ' + JSON.stringify(t4));

// same, unclosed
let t5 = mgr.extractPlainText('Preamble <think time="1.0">still reasoning about it...');
if (t5 !== 'Preamble')
  throw new Error('time-attributed unclosed leak: ' + JSON.stringify(t5));

console.log('tts thinking-strip OK');

// ── TTS: client cache is capped (entries are audio blobs, not strings) ──
{
  const m = new ttsMod.AITTSManager();
  m.available = true;
  m._provider = 'piper';
  const revoked = [];
  const oldUrl = globalThis.URL;
  const oldFetch = globalThis.fetch;
  globalThis.URL = { createObjectURL: () => 'blob:u' + Math.random().toString(36).slice(2),
                    revokeObjectURL: (u) => revoked.push(u) };
  // stats-shaped for the constructor's checkAvailability (so it can't clobber
  // `available` back to false mid-loop), blob-shaped for synthesize
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({ available: true, ready: true, provider: 'piper', speed: 1 }),
    blob: async () => 'b',
  });
  try {
    for (let i = 0; i < 40; i++) {
      await m.synthesize('sentence number ' + i + ' that is definitely long enough');
    }
  } finally {
    globalThis.URL = oldUrl;
    globalThis.fetch = oldFetch;
  }
  if (m.cache.size > 32)
    throw new Error('client TTS cache unbounded: ' + m.cache.size);
  if (revoked.length !== 40 - m.cache.size)
    throw new Error('cache eviction did not revoke URLs: revoked=' + revoked.length);
}
console.log('tts cache-cap OK');

// ── TTS: the client cache key carries the settings dimensions, so a
// voice/speed change can't return audio synthesized with the old ones ──
{
  const m = new ttsMod.AITTSManager();
  const text = 'same text, different settings';
  const k0 = m.getCacheKey(text);
  m._voice = 'en_US-ryan-low';
  const k1 = m.getCacheKey(text);
  m.playbackSpeed = 1.25;
  const k2 = m.getCacheKey(text);
  if (new Set([k0, k1, k2]).size !== 3)
    throw new Error('cache key ignores voice/speed: ' + [k0, k1, k2].join(','));
}
console.log('tts cache-key dimensions OK');

// ── Voice mode: a double start() must not double-capture the mic ──
// The stub ws opens synchronously, so the happy path completes: _ws set,
// _starting cleared, and a second click is guarded by _ws.
{
  if (!('navigator' in globalThis)) {
    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: { mediaDevices: {} },
    });
  }
  const origWS = globalThis.WebSocket;
  globalThis.WebSocket = class {
    constructor(url) { this.readyState = 1; if (this.onopen) this.onopen(); }
    static get OPEN() { return 1; }
    close() {}
    send() {}
  };
  const streamCount = { n: 0 };
  const vm = globalThis.voiceModeModule;
  const wasSecure = globalThis.isSecureContext;
  globalThis.isSecureContext = true;  // the shim defaults to false (http://localhost)
  navigator.mediaDevices.getUserMedia = async () => { streamCount.n++; return { getTracks: () => [] }; };
  vm._ws = null;
  vm._starting = false;
  const p1 = vm.start();
  // Second click while the first is still in flight (before its ws exists).
  vm.start();
  await p1;
  if (streamCount.n !== 1)
    throw new Error('double start() captured the mic twice: ' + streamCount.n);
  vm._teardown();
  globalThis.WebSocket = origWS;
  globalThis.isSecureContext = wasSecure;
}
console.log('voiceMode double-start OK');

// mic-denied path must leave the module startable again
{
  const wasSecure = globalThis.isSecureContext;
  globalThis.isSecureContext = true;
  navigator.mediaDevices.getUserMedia = async () => {
    const e = new Error('denied'); e.name = 'NotAllowedError'; throw e;
  };
  const vm = globalThis.voiceModeModule;
  vm._ws = null;
  vm._starting = false;
  await vm.start();
  globalThis.isSecureContext = wasSecure;
  if (vm._starting)
    throw new Error('mic-denied path left _starting set');
}
console.log('voiceMode denied-reset OK');

// ── TTS: streaming end-flush must never re-speak thinking or prior rounds ──
const settle = () => new Promise((r) => setTimeout(r, 250));

function makeSpeaker() {
  const m = new ttsMod.AITTSManager();
  m.available = true;
  m.autoPlay = true;
  m._provider = 'piper';
  const enqueued = [];
  m.enqueue = (text) => { enqueued.push(text); };
  return { m, enqueued };
}

// end-to-end: chat.js feeds reply-only text while streaming, then flushes the
// raw accumulated (thinking tag rewritten with a time attribute)
{
  const { m, enqueued } = makeSpeaker();
  const reply = 'Here is the summary you asked for. The tunnel is up and running.';
  const accumulated = '<think time="12.3">I need to figure out what to answer about the tunnel status and topology.</think>' + reply;
  m.streamingStart();
  m.streamingUpdate(reply);
  await settle();
  m.streamingEnd(accumulated);
  const all = enqueued.join(' | ');
  if (all.includes('figure out'))
    throw new Error('end-flush spoke thinking: ' + JSON.stringify(all));
  if (!all.includes('tunnel is up'))
    throw new Error('end-flush dropped reply: ' + JSON.stringify(all));
}

// multi-round: chat.js flushes each round at agent_step (streamingFlushRound)
// and ends with the last round's text; each round's reply must be spoken
// exactly once
{
  const { m, enqueued } = makeSpeaker();
  const r1 = 'First round answer with enough length here.';
  const r2 = 'Second round answer with enough length here.';
  m.streamingStart();
  m.streamingUpdate(r1);
  await settle();
  m.streamingFlushRound(r1); // chat.js calls this at agent_step
  m.streamingUpdate(r2);
  await settle();
  const before = enqueued.length;
  m.streamingEnd(r2);
  const flushed = enqueued.slice(before).join(' | ');
  if (flushed.includes('First round'))
    throw new Error('end-flush re-spoke round 1: ' + JSON.stringify(flushed));
  const total = enqueued.join(' | ');
  if (total.split('First round').length - 1 !== 1)
    throw new Error('round 1 count wrong: ' + JSON.stringify(enqueued));
  if (total.split('Second round').length - 1 !== 1)
    throw new Error('round 2 count wrong: ' + JSON.stringify(enqueued));
  if (total.includes('think'))
    throw new Error('flush spoke thinking: ' + JSON.stringify(total));
}

console.log('tts streaming-flush OK');
