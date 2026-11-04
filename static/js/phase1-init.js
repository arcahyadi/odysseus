/**
 * phase1-init.js — Wires all Phase 1 frontend modules.
 * Called once from static/app.js after the page is ready.
 * Requirements: 13.2
 */

import { attachReasoningTrace, ensureStreamingTraceContainer, appendStreamingNode } from './reasoning-trace.js';
import { PersonaSwitcher } from './persona-switcher.js';
import { CritiqueToggle, attachCritiqueComparison } from './critique-toggle.js';
import { renderForkBanner, attachForkButtons, attachNodeForkButton } from './fork-controls.js';
import { initVoiceSession } from './voice-session.js';

/**
 * Main entry point.  Call once after the page shell is mounted.
 */
export function initPhase1() {
  _patchMessageRenderer();
  _initActiveSession();
  // Voice session — mounts the toolbar button and probes /api/voice/status.
  // No-ops silently if STT+TTS are not configured.
  initVoiceSession().catch(() => {});
}

// ── Active session wiring ─────────────────────────────────────────────────────

function _initActiveSession() {
  // Re-run whenever the active session changes (the app fires this custom event).
  document.addEventListener('odysseus:session-changed', e => {
    const { sessionId } = e.detail || {};
    if (sessionId) _setupSession(sessionId);
  });

  // Best-effort: pick up the session id from a data attribute if the shell
  // already renders it at load time.
  const shell = document.querySelector('[data-session-id]');
  if (shell) _setupSession(shell.dataset.sessionId);
}

function _setupSession(sessionId) {
  if (!sessionId) return;

  // Persona switcher — inject into chat header
  const header = document.querySelector('.chat-header, [data-chat-header]');
  if (header) {
    try { new PersonaSwitcher(sessionId, header); } catch (_) {}
  }

  // Critique toggle — inject into chat header
  if (header) {
    try { new CritiqueToggle(sessionId, header); } catch (_) {}
  }

  // Fork banner — inject at top of the session container
  const sessionEl = document.querySelector('.chat-container, [data-chat-container]');
  if (sessionEl) {
    renderForkBanner(sessionEl, sessionId).catch(() => {});
  }
}

// ── Message renderer patch ────────────────────────────────────────────────────

/**
 * Patches the existing message-render pipeline by listening for the
 * custom event the app fires whenever a new message element is added to
 * the DOM.  This keeps Phase 1 additions completely decoupled from the
 * existing chat_routes / session rendering code (Req 13.2, 13.5).
 */
function _patchMessageRenderer() {
  // The app fires 'odysseus:message-rendered' with { messageEl, messageId, role, sessionId }
  document.addEventListener('odysseus:message-rendered', e => {
    const { messageEl, messageId, role, sessionId } = e.detail || {};
    if (!messageEl || !messageId) return;

    if (role === 'assistant') {
      // Attach reasoning trace (fetches from API, no-ops if none)
      attachReasoningTrace(messageEl, messageId).catch(() => {});

      // Attach fork button
      if (sessionId) attachForkButtons(messageEl, messageId, sessionId);
    }
  });

  // Handle streaming thinking_node events from SSE chat stream
  document.addEventListener('odysseus:thinking-node', e => {
    const { messageEl, content, index } = e.detail || {};
    if (!messageEl) return;
    const container = ensureStreamingTraceContainer(messageEl);
    appendStreamingNode(container, content, index);
  });

  // Handle critique pass completion
  document.addEventListener('odysseus:critique-applied', e => {
    const { messageEl, recordId } = e.detail || {};
    if (messageEl && recordId) attachCritiqueComparison(messageEl, recordId);
  });

  // Handle reasoning node fork button attachment
  document.addEventListener('odysseus:reasoning-node-rendered', e => {
    const { nodeEl, nodeId, messageId, sessionId } = e.detail || {};
    if (nodeEl && nodeId && messageId && sessionId) {
      attachNodeForkButton(nodeEl, nodeId, messageId, sessionId);
    }
  });
}
