// multiModel/launcher.js — entry panel for multi-model conversation threads
/**
 * Mounts into .main-content and provides:
 *   - a "new thread" form (pick >=2 chat models across endpoints + a prompt),
 *   - a history list of existing threads (open / delete).
 * Creating runs the blocking POST, then hands off to multiModelView.loadThread.
 * Mirrors compare's contract: isActive() / toggle() / open() / close(), where
 * close reloads the shell (compare tears down with a reload too).
 */

import uiModule from '../ui.js?v=20260916largetoolscroll1';
import { multiModelView } from './view.js';

const esc = uiModule.esc;
const API_BASE = window.location.origin;

// Skip non-chat models from the picker (mirrors compare/models.js prefixes).
const NON_CHAT_PREFIXES = ['tts-', 'whisper-', 'text-embedding-', 'text-moderation-', 'moderation-', 'embedding'];
const NON_CHAT_SUFFIXES = ['deep-research', '-online'];
function _isChatModel(id) {
  const lower = String(id).toLowerCase();
  if (NON_CHAT_PREFIXES.some(p => lower.startsWith(p))) return false;
  if (NON_CHAT_SUFFIXES.some(s => lower.endsWith(s) || lower.includes(s))) return false;
  return true;
}

let _active = false;
let _models = [];
let _opening = false;

function _main() {
  return document.querySelector('.main-content');
}

function isActive() {
  return _active;
}

function open() {
  if (_active) return;
  _active = true;
  _render();
}

function close() {
  // Reload the shell to restore the normal chat surface (compare does this too).
  _active = false;
  window.location.href = window.location.pathname;
}

async function toggle() {
  if (_active) { close(); return false; }
  if (_opening) return false;
  _opening = true;
  try {
    open();
    return true;
  } finally {
    _opening = false;
  }
}

async function _fetchChatModels() {
  const res = await fetch(`${API_BASE}/api/models`, { credentials: 'same-origin' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  const out = [];
  (data.items || []).forEach(item => {
    if ((item.model_type || 'llm') !== 'llm' || !item.endpoint_id) return;
    const display = item.models_display || item.models || [];
    const extraDisplay = item.models_extra_display || item.models_extra || [];
    (item.models || []).forEach((mid, i) => {
      if (_isChatModel(mid)) out.push({ id: mid, url: item.url, endpointId: item.endpoint_id, name: (display[i] || mid).split('/').pop(), endpointName: item.endpoint_name || '' });
    });
    (item.models_extra || []).forEach((mid, i) => {
      if (_isChatModel(mid)) out.push({ id: mid, url: item.url, endpointId: item.endpoint_id, name: (extraDisplay[i] || mid).split('/').pop(), endpointName: item.endpoint_name || '' });
    });
  });
  return out;
}

function _render() {
  const main = _main();
  if (!main) return;
  main.innerHTML = `
    <div class="multi-model-container" style="max-width:960px;margin:0 auto;padding:16px;display:flex;flex-direction:column;gap:16px;">
      <header class="multi-model-header" style="display:flex;align-items:center;justify-content:space-between;">
        <h2 style="margin:0;font-size:1.15rem;">Multi-model threads</h2>
        <button class="multi-model-close-btn" id="mm-launcher-close" title="Close multi-model view"
                style="padding:4px 10px;font-size:0.82em;border:1px solid var(--border);border-radius:6px;background:transparent;cursor:pointer;">Close</button>
      </header>

      <section style="border:1px solid var(--border);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:10px;">
        <div style="font-weight:600;">New thread</div>
        <div id="mm-model-list" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:6px;max-height:220px;overflow:auto;">
          <span style="opacity:0.6;">Loading models…</span>
        </div>
        <div style="font-size:0.78rem;opacity:0.7;">Select at least 2 models (each runs the same prompt concurrently).</div>
        <textarea id="mm-prompt" rows="3" placeholder="Ask every selected model the same question…"
                  style="width:100%;box-sizing:border-box;padding:8px;border:1px solid var(--border);border-radius:8px;background:transparent;color:inherit;font:inherit;resize:vertical;"></textarea>
        <div style="display:flex;align-items:center;gap:10px;">
          <button id="mm-run-btn" class="btn-secondary" style="padding:6px 16px;font-size:0.85em;cursor:pointer;">Run</button>
          <span id="mm-status" style="font-size:0.78rem;opacity:0.7;"></span>
        </div>
      </section>

      <section style="display:flex;flex-direction:column;gap:8px;">
        <div style="font-weight:600;">History</div>
        <div id="mm-history-list"><span style="opacity:0.6;">Loading…</span></div>
      </section>
    </div>
  `;

  document.getElementById('mm-launcher-close').addEventListener('click', close);
  document.getElementById('mm-run-btn').addEventListener('click', _onRun);
  _loadModels();
  _loadHistory();
}

async function _loadModels() {
  const box = document.getElementById('mm-model-list');
  if (!box) return;
  try {
    _models = await _fetchChatModels();
  } catch (err) {
    box.innerHTML = `<span style="opacity:0.7;">Could not load models: ${esc(err.message)}</span>`;
    return;
  }
  if (_models.length === 0) {
    box.innerHTML = '<span style="opacity:0.7;">No chat models found. Add model endpoints in Admin first.</span>';
    return;
  }
  box.innerHTML = _models.map((m, i) => `
    <label style="display:flex;align-items:center;gap:8px;padding:6px 8px;border:1px solid var(--border);border-radius:8px;cursor:pointer;">
      <input type="checkbox" data-idx="${i}">
      <span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
        ${esc(m.name)}${m.endpointName ? `<span style="opacity:0.6;"> · ${esc(m.endpointName)}</span>` : ''}
      </span>
    </label>
  `).join('');
}

function _selectedModels() {
  const picks = [];
  document.querySelectorAll('#mm-model-list input[type="checkbox"]:checked').forEach(cb => {
    const m = _models[Number(cb.dataset.idx)];
    if (m) picks.push(m);
  });
  return picks;
}

async function _onRun() {
  const statusEl = document.getElementById('mm-status');
  const runBtn = document.getElementById('mm-run-btn');
  const picks = _selectedModels();
  const prompt = (document.getElementById('mm-prompt').value || '').trim();

  if (picks.length < 2) { if (statusEl) statusEl.textContent = 'Select at least 2 models.'; return; }
  if (new Set(picks.map(m => m.id)).size !== picks.length) {
    if (statusEl) statusEl.textContent = 'Select each model ID only once per thread.';
    return;
  }
  if (!prompt) { if (statusEl) statusEl.textContent = 'Enter a prompt.'; return; }

  runBtn.disabled = true;
  if (statusEl) statusEl.textContent = `Running across ${picks.length} models… (this can take up to ~2 min)`;
  try {
    const result = await multiModelView.createThread(
      picks.map(m => m.id),
      prompt,
      picks.map(m => m.url),
      picks.map(m => String(m.endpointId))
    );
    await multiModelView.loadThread(result.thread_id, { onClose: _render });
  } catch (err) {
    if (statusEl) statusEl.textContent = `Failed: ${err.message}`;
    runBtn.disabled = false;
  }
}

async function _loadHistory() {
  const box = document.getElementById('mm-history-list');
  if (!box) return;
  let threads = [];
  try {
    threads = await multiModelView.listThreads();
  } catch (err) {
    box.innerHTML = `<span style="opacity:0.7;">Could not load history: ${esc(err.message)}</span>`;
    return;
  }
  if (!threads || threads.length === 0) {
    box.innerHTML = '<span style="opacity:0.6;">No threads yet.</span>';
    return;
  }
  box.innerHTML = threads.map(t => {
    const when = t.created_at ? new Date(t.created_at).toLocaleString() : '';
    const names = (t.model_ids || []).map(m => String(m).split('/').pop()).join(', ');
    return `
      <div data-id="${esc(t.id)}" style="display:flex;align-items:center;gap:12px;padding:8px 10px;border:1px solid var(--border);border-radius:8px;">
        <div style="flex:1;min-width:0;">
          <div style="font-size:0.85em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(names)}</div>
          <div style="font-size:0.72rem;opacity:0.6;">${esc(when)} · ${t.message_count} msg${t.message_count === 1 ? '' : 's'}</div>
        </div>
        <button data-act="open" class="btn-secondary" style="padding:3px 10px;font-size:0.78em;cursor:pointer;">Open</button>
        <button data-act="del" style="padding:3px 10px;font-size:0.78em;cursor:pointer;background:transparent;border:1px solid var(--border);border-radius:6px;color:inherit;">Delete</button>
      </div>`;
  }).join('');

  box.querySelectorAll('[data-id]').forEach(row => {
    const id = row.dataset.id;
    row.querySelector('[data-act="open"]').addEventListener('click', () =>
      multiModelView.loadThread(id, { onClose: _render }));
    row.querySelector('[data-act="del"]').addEventListener('click', async () => {
      if (!confirm('Delete this multi-model thread?')) return;
      try {
        await multiModelView.deleteThread(id);
      } catch (err) {
        alert('Delete failed: ' + err.message);
        return;
      }
      _loadHistory();
    });
  });
}

export { isActive, open, close, toggle };
export default { isActive, open, close, toggle };
