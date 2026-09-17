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
globalThis.WebSocket = class { readyState = 0; } ;
globalThis.AudioWorkletNode = class {};
globalThis.AudioContext = class {};
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
const state = { busy: false, ttsPlaying: false };
globalThis.sessionModule = { getCurrentSessionId: () => 's1' };
globalThis.aiTTSManager = {
  get isPlaying() { return state.ttsPlaying; },
  _processing: false,
  stop() { ttsStopped++; },
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

// 2. busy (assistant speaking) + TTS playing → barge-in: stop TTS, abort the run, queue
events.length = 0; ttsStopped = 0; state.busy = true; state.ttsPlaying = true;
vm._onTranscript('stop talking');
if (ttsStopped !== 1 || !ev('abort', true) || !ev('send', 'stop talking'))
  throw new Error('barge-in wrong: ' + JSON.stringify({ ttsStopped, events }));

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

console.log('tts thinking-strip OK');
