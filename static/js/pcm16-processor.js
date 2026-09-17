// static/js/pcm16-processor.js
// AudioWorklet: capture mic audio and emit 16 kHz mono PCM16LE frames.
//
// The AudioContext runs at the device rate (usually 48 kHz); we decimate
// to 16 kHz with a Hann-windowed-sinc kernel (a proper anti-aliased
// decimator, no library) and ship fixed 20 ms frames (640 samples /
// 1280 bytes) as transferable ArrayBuffer messages.
//
// Loaded by voiceMode.js via
// audioCtx.audioWorklet.addModule('/static/js/pcm16-processor.js').

const _FRAME = 640; // 20 ms @ 16 kHz

class PCM16Processor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.r = sampleRate / 16000;                  // decimation ratio (3 @ 48k)
    this.K = Math.max(6, Math.ceil(this.r * 3.5)); // kernel half-length (stopband rejection)
    this.w = this._designKernel();                 // 2K+1 taps, DC gain 1
    this.x = new Float32Array(0);                  // held input samples
    this.x0 = 0;                                   // stream index of x[0]
    this.nOut = 0;                                 // 16 kHz samples emitted
    this.tail = new Int16Array(0);                 // pending <20 ms output
  }

  _designKernel() {
    const K = this.K, r = this.r, L = 2 * K + 1;
    const w = new Float32Array(L);
    let sum = 0;
    for (let m = -K; m <= K; m++) {
      const t = m / r;
      const sinc = t === 0 ? 1 : Math.sin(Math.PI * t) / (Math.PI * t);
      // Raised-cosine window, 1 at center, 0 at ±K (a periodic Hann would
      // zero the center tap here and wreck the DC gain).
      const win = 0.5 + 0.5 * Math.cos(Math.PI * m / K);
      w[m + K] = sinc * win;
      sum += w[m + K];
    }
    if (sum > 1e-6) for (let i = 0; i < L; i++) w[i] /= sum;
    return w;
  }

  // Stream-absolute position, linear interpolation; 0 outside held range.
  _xAt(pos) {
    const i = Math.floor(pos) - this.x0;
    if (i < 0 || i >= this.x.length) return 0;
    if (i + 1 >= this.x.length) return this.x[i];
    const f = pos - this.x0 - i;
    return this.x[i] * (1 - f) + this.x[i + 1] * f;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch && ch.length) {
      const merged = new Float32Array(this.x.length + ch.length);
      merged.set(this.x, 0);
      merged.set(ch, this.x.length);
      this.x = merged;

      const r = this.r, K = this.K, w = this.w;
      // Emit output while input covers center + K (absolute index).
      let center = (this.nOut + 0.5) * r;
      while (center + K < this.x0 + this.x.length) {
        let s = 0;
        for (let m = -K; m <= K; m++) s += w[m + K] * this._xAt(center + m);
        this._pushOut(s);
        this.nOut++;
        center = (this.nOut + 0.5) * r;
      }
      // Compact once ~1 s of input is held. keepAbs is stream-absolute;
      // x[0] is at x0, so convert. Never drop ahead of what the next
      // output sample needs (center + K, with center >= nOut * r).
      if (this.x.length > 16000) {
        const keepAbs = Math.max(0, Math.floor(this.nOut * r) - K - 1);
        const keepFrom = Math.max(0, keepAbs - this.x0);
        this.x = this.x.subarray(keepFrom);
        this.x0 += keepFrom;
      }
    }
    return true;
  }

  _pushOut(s) {
    const v = Math.max(-1, Math.min(1, s));
    const s16 = v < 0 ? v * 0x8000 : v * 0x7fff;
    const t = new Int16Array(this.tail.length + 1);
    t.set(this.tail, 0);
    t[t.length - 1] = s16;
    this.tail = t;
    if (this.tail.length >= _FRAME) {
      const buf = new ArrayBuffer(_FRAME * 2);
      new Int16Array(buf).set(this.tail.subarray(0, _FRAME));
      this.port.postMessage(buf, [buf]);
      this.tail = this.tail.subarray(_FRAME);
    }
  }
}

registerProcessor('pcm16-processor', PCM16Processor);
