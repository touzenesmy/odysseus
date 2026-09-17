// tests/helpers/check_client_js.mjs
// Loads the voice-mode client modules under a minimal DOM shim and asserts
// they construct and wire without throwing. Run: node tests/helpers/check_client_js.mjs

import { readFileSync } from 'node:fs';

// ── DOM shim ──
const listeners = {};
const elMap = {};
function makeEl(id) {
  return {
    id, style: {}, dataset: {},
    value: '', title: '',
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    setAttribute() {}, getAttribute() { return null; },
    addEventListener(type, fn) { (listeners[id + ':' + type] ||= []).push(fn); },
    dispatchEvent() {}, focus() {},
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
