/**
 * phase2-init.js — Wires the Phase 2 (knowledge & memory) frontend modules.
 * Requirements: 9.1–9.3
 *
 * Called once from static/app.js after the page shell is ready. Mounts the
 * Digest and Knowledge-graph buttons into the chat header (same insertion
 * point voice-session uses) and exposes window.openDigestPanel /
 * window.openMemoryGraph for other UI entry points.
 */
import { openDigestPanel, getDigestPanel } from './digest-panel.js';
import { openMemoryGraph, getMemoryGraphView } from './memory-graph.js';
import { CitationRenderer } from './citations.js';
import { openPlansPanel, getPlansPanel } from './plans-panel.js';

const DIGEST_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px;"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>';
const GRAPH_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px;"><circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><circle cx="18" cy="6" r="2"/><path d="M6 9v3a3 3 0 0 0 3 3h6"/></svg>';
const PLANS_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px;"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>';

export function initPhase2() {
  try {
    _mountHeaderButtons();
  } catch (e) {
    console.warn('[phase2] header mount failed:', e);
  }
  _patchMessageRenderer();
  // Expose entry points for other UI surfaces (e.g. keyboard / overflow menu).
  window.openDigestPanel = openDigestPanel;
  window.openMemoryGraph = openMemoryGraph;
  window.openPlansPanel = openPlansPanel;
}

function _mountHeaderButtons() {
  const header = document.querySelector('.chat-header, [data-chat-header]');
  if (!header) return;
  if (header.querySelector('#p2-digest-btn') || header.querySelector('#p2-graph-btn') || header.querySelector('#p2-plans-btn')) return;

  const makeBtn = (id, title, icon, onClick) => {
    const btn = document.createElement('button');
    btn.id = id;
    btn.type = 'button';
    btn.className = 'input-icon-btn p2-icon-btn';
    btn.title = title;
    btn.setAttribute('aria-label', title);
    btn.innerHTML = icon;
    btn.addEventListener('click', onClick);
    return btn;
  };

  header.appendChild(makeBtn('p2-digest-btn', 'Morning digest', DIGEST_ICON, (e) => {
    e.preventDefault();
    openDigestPanel().catch((err) => console.warn('openDigestPanel failed:', err));
  }));
  header.appendChild(makeBtn('p2-graph-btn', 'Knowledge graph', GRAPH_ICON, (e) => {
    e.preventDefault();
    openMemoryGraph().catch((err) => console.warn('openMemoryGraph failed:', err));
  }));
  header.appendChild(makeBtn('p2-plans-btn', 'Plans — turn a document into a plan', PLANS_ICON, (e) => {
    e.preventDefault();
    openPlansPanel().catch((err) => console.warn('openPlansPanel failed:', err));
  }));
}

function _patchMessageRenderer() {
  // History renders already embed citations via chatRenderer; this listener
  // catches any message path that bypasses it (extra safety, idempotent).
  document.addEventListener('odysseus:message-rendered', (e) => {
    const { messageEl, role } = e.detail || {};
    if (!messageEl || role !== 'assistant') return;
    const dbId = messageEl.dataset.dbId || messageEl.dataset.messageId;
    if (!dbId) return;
    // No metadata here by design — persisted history re-renders citations
    // inside chatRenderer.addMessage from metadata.citations. Keep a handle
    // warm in case a caller later supplies metadata through the event.
    if (window.__p2PendingCitations && window.__p2PendingCitations[dbId]) {
      CitationRenderer.renderInto(messageEl, window.__p2PendingCitations[dbId]);
      delete window.__p2PendingCitations[dbId];
    }
  });
}

// Keep referenced singletons alive so bundlers/imports do not tree-shake them.
export { getDigestPanel, getMemoryGraphView, getPlansPanel, CitationRenderer };
export default initPhase2;
