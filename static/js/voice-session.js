/**
 * voice-session.js — Hands-free voice session for Odysseus
 * ==========================================================
 * Wires the existing STT (voiceRecorder.js) and TTS (tts-ai.js) services
 * into a continuous push-to-talk loop:
 *
 *   IDLE  →  [button press / Space]
 *   LISTENING  →  [button release / Space / silence timeout]
 *   THINKING   →  [LLM streams response]
 *   SPEAKING   →  [TTS plays response]
 *   LISTENING  →  [auto-rearm, loop continues]
 *
 * The module is purely additive — it does not modify chat.js, voiceRecorder.js,
 * or tts-ai.js. It drives them through their existing public APIs:
 *   - voiceRecorder: startRecording() / stopRecording()
 *   - tts-ai:        window.aiTTSManager.autoPlay (flag), stop()
 *   - chat.js:       sets #message value + clicks .send-btn
 *
 * Usage (from phase1-init.js or app.js):
 *   import { VoiceSession } from './voice-session.js';
 *   const vs = new VoiceSession();
 *   vs.mount(document.querySelector('.chat-input-bar'));
 *
 * The session can also be controlled programmatically:
 *   vs.start()   — enter LISTENING state
 *   vs.stop()    — exit voice mode entirely (back to IDLE)
 *   vs.toggle()  — start() if IDLE, stop() otherwise
 */

// ── State constants ─────────────────────────────────────────────────────────
const STATE = Object.freeze({
  IDLE:      'idle',
  LISTENING: 'listening',
  THINKING:  'thinking',
  SPEAKING:  'speaking',
  DISABLED:  'disabled',
});

// How long (ms) of silence before auto-submitting while listening
const SILENCE_TIMEOUT_MS = 2200;
// Min chars in transcript before auto-submit on silence
const MIN_TRANSCRIPT_CHARS = 2;

// ── SVG icons ───────────────────────────────────────────────────────────────
const ICON_MIC = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
  aria-hidden="true">
  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
  <line x1="12" y1="19" x2="12" y2="23"/>
  <line x1="8"  y1="23" x2="16" y2="23"/>
</svg>`;

const ICON_STOP = `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"
  stroke="none" aria-hidden="true">
  <rect x="5" y="5" width="14" height="14" rx="3"/>
</svg>`;

const ICON_WAVE = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
  <line x1="2"  y1="12" x2="2"  y2="12" class="vs-wave-bar vs-wave-1"/>
  <line x1="6"  y1="8"  x2="6"  y2="16" class="vs-wave-bar vs-wave-2"/>
  <line x1="10" y1="4"  x2="10" y2="20" class="vs-wave-bar vs-wave-3"/>
  <line x1="14" y1="8"  x2="14" y2="16" class="vs-wave-bar vs-wave-4"/>
  <line x1="18" y1="12" x2="18" y2="12" class="vs-wave-bar vs-wave-5"/>
  <line x1="22" y1="12" x2="22" y2="12" class="vs-wave-bar vs-wave-6"/>
</svg>`;

// ── VoiceSession class ───────────────────────────────────────────────────────
export class VoiceSession {
  constructor() {
    this._state      = STATE.IDLE;
    this._btn        = null;   // the toolbar button element
    this._indicator  = null;   // pill overlay showing current state
    this._silenceTimer = null;
    this._available  = false;  // set after probing /api/voice/status
    this._sttProvider = 'disabled';
    this._mediaRecorder = null;
    this._audioChunks   = [];
    this._abortCtrl     = null; // abort controller for the TTS-done observer

    // Bind methods used as event listeners so removeEventListener works
    this._onKeyDown   = this._onKeyDown.bind(this);
    this._onKeyUp     = this._onKeyUp.bind(this);
    this._onMsgSaved  = this._onMsgSaved.bind(this);
    this._onTtsDone   = this._onTtsDone.bind(this);
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Mount the voice session button into `containerEl` (the .chat-input-bar).
   * Probes /api/voice/status; hides the button if voice is unavailable.
   */
  async mount(containerEl) {
    if (!containerEl) return;
    this._buildButton(containerEl);
    this._buildIndicator();
    await this._probe();
  }

  /** Enter voice mode — start listening for the next utterance. */
  start() {
    if (this._state === STATE.DISABLED || !this._available) return;
    if (this._state !== STATE.IDLE) return;
    this._enterListening();
  }

  /** Exit voice mode completely and return to IDLE. */
  stop() {
    this._stopTTS();
    this._stopRecording();
    this._cancelSilenceTimer();
    this._setState(STATE.IDLE);
  }

  /** Toggle voice mode on/off. */
  toggle() {
    if (this._state === STATE.IDLE) {
      this.start();
    } else {
      this.stop();
    }
  }

  get state() { return this._state; }
  get available() { return this._available; }

  // ── Probing ────────────────────────────────────────────────────────────────

  async _probe() {
    try {
      const res = await fetch('/api/voice/status', { credentials: 'same-origin' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      this._available   = !!data.voice_available;
      this._sttProvider = data.stt?.provider || 'disabled';

      if (this._available) {
        this._setState(STATE.IDLE);
        if (this._btn) {
          this._btn.hidden = false;
          this._btn.title = 'Start voice session (Space)';
        }
      } else {
        this._setState(STATE.DISABLED);
        if (this._btn) {
          this._btn.hidden = true;
          this._btn.title = 'Voice session unavailable — enable STT and TTS in Settings';
        }
      }
    } catch (err) {
      console.warn('[VoiceSession] probe failed:', err);
      this._setState(STATE.DISABLED);
      if (this._btn) this._btn.hidden = true;
    }
  }

  // ── State machine ──────────────────────────────────────────────────────────

  _setState(next) {
    const prev = this._state;
    if (prev === next) return;
    this._state = next;
    this._updateUI(next);
    this._updateKeyboardListeners(prev, next);
    this.dispatchEvent && this.dispatchEvent(
      new CustomEvent('statechange', { detail: { prev, next } })
    );
    document.dispatchEvent(new CustomEvent('odysseus:voice-state', {
      bubbles: true,
      detail: { state: next },
    }));
  }

  _enterListening() {
    this._setState(STATE.LISTENING);
    this._startRecording();
    // Arm silence detector — if the user doesn't speak, auto-cancel after timeout
    this._cancelSilenceTimer();
    this._silenceTimer = setTimeout(() => {
      if (this._state === STATE.LISTENING) {
        this._submitRecording();
      }
    }, SILENCE_TIMEOUT_MS * 5); // generous 11s grace for first listen
  }

  _enterThinking() {
    this._setState(STATE.THINKING);
    // Enable TTS autoplay for this response
    if (window.aiTTSManager) window.aiTTSManager.autoPlay = true;
    // Listen for the message_saved SSE event — that fires when the LLM is done
    document.addEventListener('odysseus:message-saved', this._onMsgSaved, { once: true });
  }

  _enterSpeaking() {
    this._setState(STATE.SPEAKING);
    // Poll for TTS queue to drain, then re-arm microphone
    this._waitForTTSDone();
  }

  // ── Recording ─────────────────────────────────────────────────────────────

  _startRecording() {
    if (!window.isSecureContext) {
      console.warn('[VoiceSession] Microphone requires HTTPS');
      this.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      console.warn('[VoiceSession] getUserMedia not supported');
      this.stop();
      return;
    }

    this._audioChunks = [];
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        this._mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        this._mediaRecorder.ondataavailable = e => {
          if (e.data.size > 0) this._audioChunks.push(e.data);
        };
        this._mediaRecorder.onstop = () => {
          stream.getTracks().forEach(t => t.stop());
          if (this._state !== STATE.IDLE) this._processAudio();
        };
        this._mediaRecorder.start();
      })
      .catch(err => {
        console.error('[VoiceSession] Microphone error:', err);
        this.stop();
      });
  }

  _stopRecording() {
    if (this._mediaRecorder && this._mediaRecorder.state === 'recording') {
      this._mediaRecorder.stop();
    }
    this._mediaRecorder = null;
  }

  _submitRecording() {
    this._cancelSilenceTimer();
    this._stopRecording(); // triggers onstop → _processAudio
  }

  async _processAudio() {
    const blob = new Blob(this._audioChunks, { type: 'audio/webm' });
    this._audioChunks = [];

    let transcript = '';

    try {
      if (this._sttProvider === 'browser') {
        // Browser STT: best-effort via voiceRecorder module's browser transcript
        // We can't retrieve it directly; fall back to text already in input
        transcript = (document.getElementById('message')?.value || '').trim();
      } else if (this._sttProvider === 'local' || this._sttProvider.startsWith('endpoint:')) {
        transcript = await this._transcribeOnServer(blob);
      }
    } catch (err) {
      console.warn('[VoiceSession] transcription error:', err);
    }

    transcript = transcript.trim();

    if (!transcript || transcript.length < MIN_TRANSCRIPT_CHARS) {
      // Nothing heard — re-arm listening
      if (this._state !== STATE.IDLE) this._enterListening();
      return;
    }

    // Inject transcript and auto-send
    const input = document.getElementById('message');
    const sendBtn = document.querySelector('.send-btn');
    if (input && sendBtn) {
      input.value = transcript;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      this._enterThinking();
      sendBtn.click();
    } else {
      console.warn('[VoiceSession] Could not find #message or .send-btn');
      this.stop();
    }
  }

  async _transcribeOnServer(audioBlob) {
    const fd = new FormData();
    fd.append('file', audioBlob, 'audio.webm');
    const res = await fetch('/api/stt/transcribe', {
      method: 'POST',
      credentials: 'same-origin',
      body: fd,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || `STT HTTP ${res.status}`);
    }
    const data = await res.json();
    return data.text || '';
  }

  // ── TTS done detection ─────────────────────────────────────────────────────

  /**
   * Wait until the TTS queue drains, then re-arm the microphone.
   * We poll window.aiTTSManager._processing every 300ms because the TTS
   * manager doesn't emit events.  Give up after 5 minutes.
   */
  _waitForTTSDone() {
    let elapsed = 0;
    const POLL = 300;
    const MAX  = 5 * 60 * 1000;

    // Give TTS a moment to actually start before we start polling
    const timer = setInterval(() => {
      elapsed += POLL;

      const mgr = window.aiTTSManager;
      const done = !mgr || (!mgr._processing && !mgr.isPlaying);

      if (done || elapsed >= MAX || this._state === STATE.IDLE) {
        clearInterval(timer);
        if (window.aiTTSManager) window.aiTTSManager.autoPlay = false;
        if (this._state === STATE.SPEAKING) {
          // Re-arm for next utterance
          this._enterListening();
        }
      }
    }, POLL);

    // Store cleanup reference
    this._ttsPoller = timer;
  }

  _stopTTS() {
    if (this._ttsPoller) {
      clearInterval(this._ttsPoller);
      this._ttsPoller = null;
    }
    if (window.aiTTSManager) {
      window.aiTTSManager.stop();
      window.aiTTSManager.autoPlay = false;
    }
  }

  // ── Event handlers ─────────────────────────────────────────────────────────

  /**
   * Fired by chat.js via the custom event 'odysseus:message-saved' when the
   * LLM response is persisted. Transition to SPEAKING.
   */
  _onMsgSaved() {
    if (this._state === STATE.THINKING) {
      this._enterSpeaking();
    }
  }

  _onTtsDone() {
    if (this._state === STATE.SPEAKING) {
      if (window.aiTTSManager) window.aiTTSManager.autoPlay = false;
      this._enterListening();
    }
  }

  /** Space: start on press, submit on release (push-to-talk). */
  _onKeyDown(e) {
    if (e.code !== 'Space') return;
    if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
    if (this._state === STATE.IDLE) {
      e.preventDefault();
      this._enterListening();
    }
  }

  _onKeyUp(e) {
    if (e.code !== 'Space') return;
    if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
    if (this._state === STATE.LISTENING) {
      e.preventDefault();
      this._submitRecording();
    }
  }

  _cancelSilenceTimer() {
    if (this._silenceTimer) {
      clearTimeout(this._silenceTimer);
      this._silenceTimer = null;
    }
  }

  // ── Keyboard listener management ───────────────────────────────────────────

  _updateKeyboardListeners(prev, next) {
    const wasActive = prev !== STATE.IDLE && prev !== STATE.DISABLED;
    const isActive  = next !== STATE.IDLE && next !== STATE.DISABLED;

    if (!wasActive && isActive) {
      document.addEventListener('keydown', this._onKeyDown);
      document.addEventListener('keyup',   this._onKeyUp);
    } else if (wasActive && !isActive) {
      document.removeEventListener('keydown', this._onKeyDown);
      document.removeEventListener('keyup',   this._onKeyUp);
    }
  }

  // ── DOM / UI ───────────────────────────────────────────────────────────────

  _buildButton(containerEl) {
    // Find the right-side controls row
    const rightBar = containerEl.querySelector('.chat-input-right');
    if (!rightBar) {
      console.warn('[VoiceSession] .chat-input-right not found; appending to containerEl');
    }
    const target = rightBar || containerEl;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id   = 'voice-session-btn';
    btn.className = 'voice-session-btn input-icon-btn';
    btn.setAttribute('aria-label', 'Voice session');
    btn.setAttribute('aria-pressed', 'false');
    btn.title  = 'Voice session';
    btn.hidden = true; // shown after probe confirms availability
    btn.innerHTML = ICON_MIC;

    btn.addEventListener('click', () => this.toggle());

    // Insert before the send button if present, otherwise append
    const sendBtn = target.querySelector('.send-btn') || target.querySelector('button[type="submit"]');
    if (sendBtn) {
      target.insertBefore(btn, sendBtn);
    } else {
      target.appendChild(btn);
    }

    this._btn = btn;
  }

  _buildIndicator() {
    const existing = document.getElementById('voice-session-indicator');
    if (existing) { this._indicator = existing; return; }

    const el = document.createElement('div');
    el.id = 'voice-session-indicator';
    el.className = 'voice-session-indicator vs-hidden';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');

    // Waveform + label + stop button
    el.innerHTML = `
      <span class="vs-wave-wrap" aria-hidden="true">${ICON_WAVE}</span>
      <span class="vs-label">Listening…</span>
      <button type="button" class="vs-stop-btn" aria-label="Stop voice session">
        ${ICON_STOP}
      </button>
    `;

    el.querySelector('.vs-stop-btn').addEventListener('click', () => this.stop());
    document.body.appendChild(el);
    this._indicator = el;
  }

  _updateUI(state) {
    const btn = this._btn;
    const ind = this._indicator;

    // Button icon + aria
    if (btn) {
      btn.setAttribute('aria-pressed', state !== STATE.IDLE ? 'true' : 'false');
      btn.className = `voice-session-btn input-icon-btn vs-state-${state}`;
      btn.innerHTML = (state === STATE.IDLE || state === STATE.DISABLED) ? ICON_MIC : ICON_STOP;
    }

    // Indicator pill
    if (!ind) return;
    const label = ind.querySelector('.vs-label');

    if (state === STATE.IDLE || state === STATE.DISABLED) {
      ind.classList.add('vs-hidden');
      return;
    }

    ind.classList.remove('vs-hidden');

    const labels = {
      [STATE.LISTENING]: 'Listening…',
      [STATE.THINKING]:  'Thinking…',
      [STATE.SPEAKING]:  'Speaking…',
    };
    if (label) label.textContent = labels[state] || state;

    // Swap waveform animation speed by state
    ind.dataset.vsState = state;
  }
}

// ── chat.js bridge ────────────────────────────────────────────────────────────
/**
 * Patch chat.js to fire 'odysseus:message-saved' when a message is persisted.
 * chat.js already handles `json.type === 'message_saved'` in its SSE loop;
 * we observe the DOM mutation it causes (it sets data-db-id on the bubble)
 * so we don't need to touch chat.js at all.
 *
 * We use a MutationObserver on #chat-history looking for elements that gain
 * a `data-db-id` attribute — this fires immediately after chat.js processes
 * the message_saved SSE event.
 */
let _msgSavedObserver = null;

export function patchChatForVoice() {
  if (_msgSavedObserver) return;
  const chatHistory = document.getElementById('chat-history');
  if (!chatHistory) return;

  _msgSavedObserver = new MutationObserver(mutations => {
    for (const m of mutations) {
      if (m.type === 'attributes' && m.attributeName === 'data-db-id') {
        document.dispatchEvent(new CustomEvent('odysseus:message-saved', {
          bubbles: false,
          detail: { id: m.target.dataset.dbId },
        }));
      }
    }
  });

  _msgSavedObserver.observe(chatHistory, {
    subtree: true,
    attributes: true,
    attributeFilter: ['data-db-id'],
  });
}

// ── Module-level singleton + auto-init helper ─────────────────────────────────

let _instance = null;

/**
 * Get (or create) the module-level VoiceSession singleton.
 * Call initVoiceSession() from phase1-init.js / app.js after the chat
 * input bar is in the DOM.
 */
export function getVoiceSession() {
  if (!_instance) _instance = new VoiceSession();
  return _instance;
}

export async function initVoiceSession() {
  // Patch chat.js bridge first
  patchChatForVoice();

  // Wait for DOM to be ready
  const attach = () => {
    const bar = document.querySelector('.chat-input-bar');
    if (bar) {
      const vs = getVoiceSession();
      vs.mount(bar);
    } else {
      // Retry once on DOMContentLoaded or after a tick
      requestAnimationFrame(() => {
        const b = document.querySelector('.chat-input-bar');
        if (b) getVoiceSession().mount(b);
      });
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attach, { once: true });
  } else {
    attach();
  }
}
