// tests/helpers/check_pcm_processor.mjs
// Verifies the AudioWorklet decimator: DC gain, 440 Hz pass, 10 kHz stop,
// frame cadence. Run: node tests/helpers/check_pcm_processor.mjs

import { readFileSync } from 'node:fs';

const frames = [];
globalThis.sampleRate = 48000;
globalThis.AudioWorkletProcessor = class {
  constructor() { this.port = { postMessage: (buf) => frames.push(new Int16Array(buf)) }; }
};
const _reg = [];
globalThis.registerProcessor = (name, cls) => _reg.push([name, cls]);

let src = readFileSync(new URL('../../static/js/pcm16-processor.js', import.meta.url), 'utf8');
// The worklet file calls registerProcessor at top level; node has no global
// sampleRate constant — we set it above.
await import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'));
if (_reg.length !== 1 || _reg[0][0] !== 'pcm16-processor')
  throw new Error('pcm16-processor not registered');
const cls = _reg[0][1];

const feed = (p, arr) => {
  for (let i = 0; i < arr.length; i += 128)
    p.process([[arr.subarray(i, Math.min(i + 128, arr.length))]]);
};
const peak = (a) => { let m = 0; for (const v of a) m = Math.max(m, Math.abs(v)); return m; };
const freq = (out) => {
  let zc = 0;
  for (let i = 1; i < out.length; i++) if ((out[i - 1] < 0) !== (out[i] < 0)) zc++;
  return zc / 2 / (out.length / 16000);
};
const tone = (f, sr, secs, a = 0.9) => {
  const t = new Float32Array(sr * secs);
  for (let i = 0; i < t.length; i++) t[i] = a * Math.sin(2 * Math.PI * f * i / sr);
  return t;
};
const flat = () => frames.flatMap((f) => Array.from(f));
const checks = [];

// DC
{
  frames.length = 0;
  const p = new cls();
  feed(p, new Float32Array(48000).fill(0.5));
  const last = flat()[flat().length - 1];
  checks.push(['DC gain ~0.5', Math.abs(last - 16384) < 60, `got ${last}`]);
}
// 440 Hz passes at the right frequency + amplitude
{
  frames.length = 0;
  const p = new cls();
  feed(p, tone(440, 48000, 2));
  const out = flat();
  checks.push(['440 Hz count', out.length > 31000, `n=${out.length}`]);
  checks.push(['440 Hz freq', Math.abs(freq(out) - 440) < 3, `got ${freq(out).toFixed(1)}`]);
  checks.push(['440 Hz amplitude', peak(out) > 20000, `peak=${peak(out)}`]);
}
// 10 kHz must be attenuated (< 25% of full scale)
{
  frames.length = 0;
  const p = new cls();
  feed(p, tone(10000, 48000, 1));
  const pk = peak(flat());
  checks.push(['10 kHz stopband', pk < 9000, `peak=${pk}`]);
}
// cadence: 2 s of 48 kHz → every emitted frame is exactly 640 samples
// (20 ms @ 16 kHz) and the total rate is 16 kHz within one frame.
// (A causal decimator holds a K-sample lookahead, so the final partial
// frame sits in the processor tail — the rate check accounts for it.)
{
  frames.length = 0;
  const p = new cls();
  feed(p, tone(200, 48000, 2));
  const sizes = frames.every((f) => f.length === 640);
  const total = frames.length * 640 + p.tail.length;
  const rate_ok = Math.abs(total - 32000) <= 640;
  checks.push(['frame cadence', sizes && rate_ok,
              `frames=${frames.length} total=${total} (expect ~32000)`]);
}

let fail = 0;
for (const [name, ok, detail] of checks) {
  if (!ok) fail++;
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name} (${detail})`);
}
if (fail) process.exit(1);
console.log('pcm16 OK');
