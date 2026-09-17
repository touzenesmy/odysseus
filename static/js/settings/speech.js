// Text-to-speech and speech-to-text settings panels.
// Extracted verbatim from static/js/settings.js. Behaviour is unchanged: the
// functions moved, their bodies did not. settings.js imports them and calls
// them from the same places, so load order and init sequence are untouched.

import { byId as el } from './dom.js';
import { postSettings as _postSettings } from './api.js';

export async function initTtsSettings() {
  var provSel = el('set-ttsProviderSelect');
  var modelSelect = el('set-ttsModelSelect');
  var modelInput = el('set-ttsModelInput');
  var voiceSelect = el('set-ttsVoiceSelect');
  var voiceInput = el('set-ttsVoiceInput');
  var modelRow = el('set-ttsModelRow');
  var voiceRow = el('set-ttsVoiceRow');
  var speedSelect = el('set-ttsSpeedSelect');
  var speedRow = el('set-ttsSpeedRow');
  var ttsMsg = el('set-ttsSettingsMsg');
  var ttsEnabledToggle = el('set-ttsEnabledToggle');
  var piperVoiceSelect = el('set-ttsPiperVoiceSelect');
  var piperVoiceRow = el('set-ttsPiperVoiceRow');
  var piperAuditionBtn = el('set-ttsPiperAuditionBtn');
  var ttsConfigWrap = provSel ? provSel.closest('div[style*="flex-direction"]') : null;

  function isEndpoint() { return provSel.value.startsWith('endpoint:'); }
  function getModel() { return isEndpoint() ? modelSelect.value : modelInput.value; }
  function getVoice() {
    if (provSel.value === 'piper') return piperVoiceSelect ? piperVoiceSelect.value : '';
    return isEndpoint() ? voiceSelect.value : voiceInput.value;
  }

  function updateVisibility() {
    var prov = provSel.value;
    modelRow.style.display = prov.startsWith('endpoint:') ? 'flex' : 'none';
    voiceRow.style.display = (prov === 'disabled' || prov === 'piper') ? 'none' : 'flex';
    speedRow.style.display = prov === 'disabled' ? 'none' : 'flex';
    if (piperVoiceRow) piperVoiceRow.style.display = prov === 'piper' ? 'flex' : 'none';
    if (isEndpoint()) {
      modelSelect.style.display = ''; modelInput.style.display = 'none';
      voiceSelect.style.display = ''; voiceInput.style.display = 'none';
    } else {
      modelSelect.style.display = 'none'; modelInput.style.display = '';
      voiceSelect.style.display = 'none'; voiceInput.style.display = prov === 'disabled' ? 'none' : '';
    }
  }

  async function loadPiperVoices() {
    if (!piperVoiceSelect) return;
    try {
      var res = await fetch('/api/tts/voices', { credentials: 'same-origin' });
      var data = await res.json();
      var voices = data.voices || [];
      piperVoiceSelect.innerHTML = '';
      voices.forEach(function(v) {
        var opt = document.createElement('option');
        opt.value = v.name;
        opt.textContent = v.name + (v.language ? ' \u2014 ' + v.language : '');
        piperVoiceSelect.appendChild(opt);
      });
      var saved = (settings && settings.tts_voice) || '';
      if (saved && voices.some(function(v) { return v.name === saved; })) {
        piperVoiceSelect.value = saved;
      } else if (voices.length) {
        piperVoiceSelect.value = voices[0].name;
      }
      piperVoiceSelect.disabled = !voices.length;
    } catch (e) { console.warn('Failed to load Piper voices', e); }
  }

  var ttsKeywords = ['tts', 'audio'];
  try {
    var epRes = await fetch('/api/model-endpoints', { credentials: 'same-origin' });
    var endpoints = await epRes.json();
    endpoints.forEach(function(ep) {
      if (!ep.is_enabled) return;
      var hasTTS = (ep.models || []).some(m => ttsKeywords.some(kw => m.toLowerCase().includes(kw)));
      if (!hasTTS) return;
      var opt = document.createElement('option'); opt.value = 'endpoint:' + ep.id; opt.textContent = ep.name + ' (API)'; provSel.appendChild(opt);
    });
  } catch (e) { console.warn('Failed to load endpoints for TTS', e); }

  try {
    var settingsRes = await fetch('/api/auth/settings', { credentials: 'same-origin' });
    var settings = await settingsRes.json();
    if (settings.tts_provider) provSel.value = settings.tts_provider;
    if (settings.tts_model) { modelSelect.value = settings.tts_model; modelInput.value = settings.tts_model; }
    if (settings.tts_voice) { voiceSelect.value = settings.tts_voice; voiceInput.value = settings.tts_voice; }
    if (settings.tts_speed) { speedSelect.value = settings.tts_speed; }
    if (ttsEnabledToggle) ttsEnabledToggle.checked = settings.tts_enabled !== false;
  } catch (e) { console.warn('Failed to load TTS settings', e); }

  function syncTtsDisabled() {
    var off = ttsEnabledToggle && !ttsEnabledToggle.checked;
    var card = ttsEnabledToggle ? ttsEnabledToggle.closest('.admin-card') : null;
    if (card) card.style.opacity = off ? '0.45' : '';
    if (ttsConfigWrap) ttsConfigWrap.style.pointerEvents = off ? 'none' : '';
  }
  syncTtsDisabled();
  updateVisibility();
  if (provSel && provSel.value === 'piper') loadPiperVoices();

  async function saveTTS() {
    try {
      await _postSettings({ tts_enabled: ttsEnabledToggle ? ttsEnabledToggle.checked : true, tts_provider: provSel.value, tts_model: getModel() || 'tts-1', tts_voice: getVoice() || 'alloy', tts_speed: speedSelect.value || '1' });
      ttsMsg.textContent = 'Saved'; ttsMsg.style.color = 'var(--fg)'; setTimeout(() => { ttsMsg.textContent = ''; }, 2000);
      if (window.aiTTSManager) window.aiTTSManager.checkAvailability();
    } catch (e) { ttsMsg.textContent = e.status === 403 ? 'Admin access is required to change these settings.' : 'Failed to save'; ttsMsg.style.color = 'var(--red)'; }
  }

  async function saveAndClearCache() {
    await saveTTS();
    fetch('/api/tts/clear-cache', { method: 'POST', credentials: 'same-origin' }).catch(function(){});
  }

  provSel.addEventListener('change', async function() {
    var prov = provSel.value;
    if (prov === 'local') voiceInput.value = 'af_heart';
    else if (isEndpoint()) { voiceSelect.value = 'alloy'; modelSelect.value = 'tts-1'; }
    else if (prov === 'piper') { await loadPiperVoices(); }
    else if (prov === 'browser') { voiceInput.value = ''; voiceInput.placeholder = 'OS default voice'; }
    updateVisibility();
    saveTTS();
  });
  modelSelect.addEventListener('change', saveAndClearCache);
  modelInput.addEventListener('change', saveTTS);
  voiceSelect.addEventListener('change', saveAndClearCache);
  voiceInput.addEventListener('change', saveTTS);
  speedSelect.addEventListener('change', saveAndClearCache);
  if (piperVoiceSelect) piperVoiceSelect.addEventListener('change', saveAndClearCache);
  if (ttsEnabledToggle) ttsEnabledToggle.addEventListener('change', function() { syncTtsDisabled(); saveTTS(); });

  // Piper voice audition — synthesizes a fixed sentence with the selected
  // voice via the voice override (settings are not written).
  if (piperAuditionBtn) {
    var auditionAudio = null;
    piperAuditionBtn.addEventListener('click', async function() {
      var name = piperVoiceSelect ? piperVoiceSelect.value : '';
      if (!name) {
        ttsMsg.textContent = 'No Piper voice cached'; ttsMsg.style.color = 'var(--red, #e55)';
        setTimeout(function() { ttsMsg.textContent = ''; }, 2000); return;
      }
      try {
        if (auditionAudio) { auditionAudio.pause(); auditionAudio = null; }
        var res = await fetch('/api/tts/synthesize', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: 'Hello, this is how I sound. I live on your server and speak at conversation speed.',
            format: 'audio', voice: name
          })
        });
        if (!res.ok) {
          var err = await res.json().catch(function() { return {}; });
          throw new Error(err.detail?.message || 'Synthesis failed');
        }
        var blob = await res.blob();
        var url = URL.createObjectURL(blob);
        auditionAudio = new Audio(url);
        auditionAudio.onended = function() { URL.revokeObjectURL(url); auditionAudio = null; };
        auditionAudio.onerror = function() { URL.revokeObjectURL(url); auditionAudio = null; };
        await auditionAudio.play().catch(function(e) { throw new Error('Playback failed: ' + e.message); });
      } catch (e) {
        ttsMsg.textContent = 'Audition failed: ' + e.message; ttsMsg.style.color = 'var(--red, #e55)';
        setTimeout(function() { ttsMsg.textContent = ''; }, 2500);
      }
    });
  }

  // Preview / test button
  var previewBtn = el('set-ttsPreviewBtn');
  if (previewBtn) {
    var previewAudio = null;
    var previewPlaying = false;
    function resetPreview() { previewPlaying = false; previewBtn.textContent = 'Preview'; previewBtn.style.borderColor = ''; }

    previewBtn.addEventListener('click', async function() {
      if (previewPlaying) {
        if (previewAudio) { previewAudio.pause(); previewAudio = null; }
        window.speechSynthesis.cancel();
        resetPreview(); return;
      }
      var prov = provSel.value;
      if (prov === 'disabled') {
        ttsMsg.textContent = 'Select a provider first'; ttsMsg.style.color = 'var(--red, #e55)';
        setTimeout(function() { ttsMsg.textContent = ''; }, 2000); return;
      }
      var testText = 'Hello, this is a test of text to speech.';
      previewPlaying = true; previewBtn.textContent = 'Loading...';
      try {
        if (prov === 'browser') {
          if (!('speechSynthesis' in window)) throw new Error('Browser TTS not supported');
          var utt = new SpeechSynthesisUtterance(testText);
          var voiceVal = getVoice();
          if (voiceVal) {
            var voices = window.speechSynthesis.getVoices();
            var target = voiceVal.toLowerCase();
            var match = voices.find(function(v) { return v.name.toLowerCase() === target; }) ||
                        voices.find(function(v) { return v.name.toLowerCase().includes(target); });
            if (match) utt.voice = match;
          }
          utt.rate = parseFloat(speedSelect.value) || 1;
          previewBtn.textContent = 'Stop'; previewBtn.style.borderColor = 'var(--red, #e55)';
          await new Promise(function(resolve, reject) {
            utt.onend = resolve;
            utt.onerror = function(e) { reject(new Error('Browser TTS: ' + e.error)); };
            window.speechSynthesis.speak(utt);
          });
        } else {
          var previewBody = { text: testText, format: 'audio' };
          if (prov === 'piper' && piperVoiceSelect) previewBody.voice = piperVoiceSelect.value;
          var res = await fetch('/api/tts/synthesize', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(previewBody)
          });
          if (!res.ok) { var err = await res.json().catch(function() { return {}; }); throw new Error(err.detail?.message || 'Synthesis failed'); }
          var blob = await res.blob();
          var url = URL.createObjectURL(blob);
          previewAudio = new Audio(url);
          previewBtn.textContent = 'Stop'; previewBtn.style.borderColor = 'var(--red, #e55)';
          await new Promise(function(resolve, reject) {
            previewAudio.onended = function() { URL.revokeObjectURL(url); previewAudio = null; resolve(); };
            previewAudio.onerror = function() { URL.revokeObjectURL(url); previewAudio = null; reject(new Error('Playback failed')); };
            previewAudio.play().catch(reject);
          });
        }
      } catch (e) {
        ttsMsg.textContent = 'Preview failed: ' + e.message; ttsMsg.style.color = 'var(--red, #e55)';
        setTimeout(function() { ttsMsg.textContent = ''; }, 3000);
      } finally {
        resetPreview();
      }
    });
  }
}

export async function initSttSettings() {
  var provSel = el('set-sttProviderSelect');
  var modelSelect = el('set-sttModelSelect');
  var modelInput = el('set-sttModelInput');
  var modelRow = el('set-sttModelRow');
  var langRow = el('set-sttLangRow');
  var langInput = el('set-sttLangInput');
  var sttMsg = el('set-sttSettingsMsg');
  var sttEnabledToggle = el('set-sttEnabledToggle');
  var sttConfigWrap = el('set-sttConfigWrap');
  // STT was removed from AI Defaults — bail if the UI isn't present.
  if (!provSel) return;

  function isEndpoint() { return provSel.value.startsWith('endpoint:'); }
  function getModel() { return isEndpoint() ? modelInput.value : modelSelect.value; }

  function updateVisibility() {
    var prov = provSel.value;
    var showModel = prov === 'local' || prov.startsWith('endpoint:');
    var showLang = prov !== 'disabled';
    modelRow.style.display = showModel ? 'flex' : 'none';
    langRow.style.display = showLang ? 'flex' : 'none';
    if (isEndpoint()) {
      modelSelect.style.display = 'none'; modelInput.style.display = '';
    } else {
      modelSelect.style.display = ''; modelInput.style.display = 'none';
    }
  }

  function syncSttDisabled() {
    var off = sttEnabledToggle && !sttEnabledToggle.checked;
    var card = sttEnabledToggle ? sttEnabledToggle.closest('.admin-card') : null;
    if (card) card.style.opacity = off ? '0.45' : '';
    if (sttConfigWrap) sttConfigWrap.style.pointerEvents = off ? 'none' : '';
  }

  // Effective provider: if toggle is off, treat as disabled regardless of provider select
  function effectiveProvider() {
    if (sttEnabledToggle && !sttEnabledToggle.checked) return 'disabled';
    return provSel.value;
  }

  // Add API endpoints that might support STT
  try {
    var epRes = await fetch('/api/model-endpoints', { credentials: 'same-origin' });
    var endpoints = await epRes.json();
    endpoints.forEach(function(ep) {
      if (!ep.is_enabled) return;
      var opt = document.createElement('option'); opt.value = 'endpoint:' + ep.id; opt.textContent = ep.name + ' (API)'; provSel.appendChild(opt);
    });
  } catch (e) { console.warn('Failed to load endpoints for STT', e); }

  // Load saved settings
  try {
    var settingsRes = await fetch('/api/auth/settings', { credentials: 'same-origin' });
    var settings = await settingsRes.json();
    if (settings.stt_provider) provSel.value = settings.stt_provider;
    if (settings.stt_model) { modelSelect.value = settings.stt_model; modelInput.value = settings.stt_model; }
    if (settings.stt_language) langInput.value = settings.stt_language;
    if (sttEnabledToggle) sttEnabledToggle.checked = settings.stt_enabled !== false;
  } catch (e) { console.warn('Failed to load STT settings', e); }

  syncSttDisabled();
  updateVisibility();

  async function saveSTT() {
    try {
      var enabled = sttEnabledToggle ? sttEnabledToggle.checked : false;
      await _postSettings({ stt_enabled: enabled, stt_provider: provSel.value, stt_model: getModel() || 'base', stt_language: langInput.value.trim() });
      sttMsg.textContent = 'Saved'; sttMsg.style.color = 'var(--fg)'; setTimeout(() => { sttMsg.textContent = ''; }, 2000);
      // Notify voiceRecorder of effective provider and update send button icon
      if (window.voiceRecorderModule) window.voiceRecorderModule._sttProvider = effectiveProvider();
      if (window._updateSendBtnIcon) window._updateSendBtnIcon();
    } catch (e) { sttMsg.textContent = e.status === 403 ? 'Admin access is required to change these settings.' : 'Failed to save'; sttMsg.style.color = 'var(--red)'; }
  }

  provSel.addEventListener('change', function() { updateVisibility(); saveSTT(); });
  modelSelect.addEventListener('change', saveSTT);
  modelInput.addEventListener('change', saveSTT);
  langInput.addEventListener('change', saveSTT);
  if (sttEnabledToggle) sttEnabledToggle.addEventListener('change', function() { syncSttDisabled(); saveSTT(); });

  /* ── Voice Mode (Phase 2) — lives in this card, saves via the same path ── */
  var vmToggle = el('set-voiceModeToggle');
  var vmStatus = el('set-voiceModeStatus');
  var vmTestBtn = el('set-voiceModeTestBtn');
  var vmWrap = el('set-voiceModeWrap');
  var vadInput = el('set-vadSilenceInput');
  if (vmToggle) {
    try {
      var vsRes = await fetch('/api/auth/settings', { credentials: 'same-origin' });
      var vs = await vsRes.json();
      vmToggle.checked = vs.voice_mode_enabled === true;
      if (vadInput && vs.vad_silence_ms) vadInput.value = vs.vad_silence_ms;
    } catch (e) { /* keep defaults */ }

    function syncVmDisabled() {
      var off = !vmToggle.checked;
      if (vmWrap) vmWrap.style.pointerEvents = off ? 'none' : '';
      if (vmWrap) vmWrap.style.opacity = off ? '0.45' : '';
    }
    syncVmDisabled();
    vmToggle.addEventListener('change', function() {
      syncVmDisabled();
      saveVoiceMode();
    });
    if (vadInput) vadInput.addEventListener('change', saveVoiceMode);
    async function saveVoiceMode() {
      try {
        var v = parseInt(vadInput.value, 10);
        await _postSettings({
          voice_mode_enabled: vmToggle.checked,
          vad_silence_ms: isNaN(v) ? 500 : Math.max(200, Math.min(3000, v)),
        });
        vmStatus.textContent = 'Saved';
        vmStatus.style.color = 'var(--fg)';
        setTimeout(function() { vmStatus.textContent = ''; }, 2000);
        if (window.voiceModeModule) window.voiceModeModule.checkAvailability();
      } catch (e) {
        vmStatus.textContent = 'Failed to save';
        vmStatus.style.color = 'var(--red)';
      }
    }
    // Microphone sanity check: request the mic and report what we hear.
    if (vmTestBtn) vmTestBtn.addEventListener('click', async function() {
      vmStatus.textContent = 'Listening… (speak now)';
      vmStatus.style.color = 'var(--fg)';
      var stream = null;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        var ctx = new (window.AudioContext || window.webkitAudioContext)();
        var src = ctx.createMediaStreamSource(stream);
        var an = ctx.createAnalyser();
        an.fftSize = 2048;
        src.connect(an);
        var buf = new Float32Array(an.fftSize);
        var peak = 0;
        await new Promise(function(resolve) {
          var t0 = Date.now();
          (function tick() {
            an.getFloatTimeDomainData(buf);
            for (var i = 0; i < buf.length; i++) peak = Math.max(peak, Math.abs(buf[i]));
            if (Date.now() - t0 >= 1500) resolve();
            else if (document.hidden) { resolve(); return; }
            else requestAnimationFrame(tick);
          })();
        });
        ctx.close();
        stream.getTracks().forEach(function(t) { t.stop(); stream = null; });
        if (peak > 0.02) {
          vmStatus.textContent = 'Microphone OK — audio detected (peak ' + peak.toFixed(2) + ')';
          vmStatus.style.color = 'var(--green, #4c4)';
        } else {
          vmStatus.textContent = 'Microphone OK — but no audio detected. Speak while testing.';
          vmStatus.style.color = 'var(--red, #e55)';
        }
      } catch (e) {
        vmStatus.textContent = e.name === 'NotAllowedError' ? 'Microphone permission denied' : 'Mic error: ' + e.message;
        vmStatus.style.color = 'var(--red, #e55)';
        if (stream) stream.getTracks().forEach(function(t) { t.stop(); });
      }
    });
  }
}
