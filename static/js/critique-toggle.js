/**
 * critique-toggle.js — Per-session critique toggle + comparison panel.
 * Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
 */

export class CritiqueToggle {
  /**
   * @param {string} sessionId
   * @param {HTMLElement} headerEl - element containing a .critique-toggle <input type="checkbox">
   */
  constructor(sessionId, headerEl) {
    this.sessionId = sessionId;
    this.headerEl = headerEl;
    this._toggle = headerEl.querySelector('.critique-toggle');
    if (this._toggle) {
      this._toggle.addEventListener('change', () => this._onChange());
    }
    this._syncState();
  }

  // ── Private ──────────────────────────────────────────────────────────────

  async _syncState() {
    try {
      const res = await fetch(`/api/sessions/${this.sessionId}/critique`);
      if (!res.ok) return;
      const cfg = await res.json();
      if (this._toggle) this._toggle.checked = !!cfg.enabled;
    } catch (_) {}
  }

  async _onChange() {
    const enabled = this._toggle ? this._toggle.checked : false;
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), 2000);
    try {
      const res = await fetch(`/api/sessions/${this.sessionId}/critique`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (_err) {
      // Requirement 8.4: revert and show error if not acknowledged within 2s
      if (this._toggle) this._toggle.checked = !enabled;
      _showToast('Failed to update critique setting', 'error');
    } finally {
      clearTimeout(tid);
    }
  }
}

/**
 * Attach a "✓ Critiqued" badge to a message element that triggers a
 * side-by-side comparison panel.
 *
 * @param {HTMLElement} messageEl
 * @param {string} recordId - CritiquePassRecord id
 */
export function attachCritiqueComparison(messageEl, recordId) {
  if (!messageEl || !recordId) return;
  const meta = messageEl.querySelector('.message-meta');
  if (!meta) return;

  const badge = document.createElement('button');
  badge.className = 'critiqued-badge';
  badge.setAttribute('aria-label', 'Show critique comparison');
  badge.textContent = '✓ Critiqued';
  badge.addEventListener('click', e => {
    e.stopPropagation();
    _toggleComparisonPanel(messageEl, recordId);
  });
  meta.appendChild(badge);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function _toggleComparisonPanel(messageEl, recordId) {
  const existing = messageEl.querySelector('.critique-comparison-panel');
  if (existing) { existing.remove(); return; }

  // Show loading state
  const loadingDiv = document.createElement('div');
  loadingDiv.className = 'critique-comparison-panel critique-comparison-panel--loading';
  loadingDiv.textContent = 'Loading comparison…';
  messageEl.appendChild(loadingDiv);

  try {
    const res = await fetch(`/api/critique/records/${encodeURIComponent(recordId)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const record = await res.json();
    loadingDiv.remove();
    _renderComparisonPanel(messageEl, record);
  } catch (err) {
    loadingDiv.textContent = 'Failed to load comparison.';
    console.warn('Critique comparison fetch failed:', err);
  }
}

function _renderComparisonPanel(messageEl, record) {
  const panel = document.createElement('div');
  panel.className = 'critique-comparison-panel';

  const closeBtn = document.createElement('button');
  closeBtn.className = 'critique-comparison-panel__close';
  closeBtn.textContent = '✕';
  closeBtn.setAttribute('aria-label', 'Close comparison');
  closeBtn.addEventListener('click', () => panel.remove());

  const title = document.createElement('h4');
  title.className = 'critique-comparison-panel__title';
  title.textContent = 'Critique Comparison';

  const grid = document.createElement('div');
  grid.className = 'critique-comparison-panel__grid';

  const origCol = _makeColumn('Original Draft', record.original_draft || '');
  const revisedCol = _makeColumn('Revised Response', record.revised_response || record.original_draft || '');
  grid.appendChild(origCol);
  grid.appendChild(revisedCol);

  const footer = document.createElement('p');
  footer.className = 'critique-comparison-panel__footer';
  footer.textContent = `Primary: ${record.primary_model}  ·  Critique: ${record.critique_model}`;

  panel.appendChild(closeBtn);
  panel.appendChild(title);
  panel.appendChild(grid);
  panel.appendChild(footer);
  messageEl.appendChild(panel);
}

function _makeColumn(heading, text) {
  const col = document.createElement('div');
  col.className = 'critique-comparison-panel__col';
  const h = document.createElement('strong');
  h.textContent = heading;
  const p = document.createElement('pre');
  p.className = 'critique-comparison-panel__text';
  p.textContent = text;
  col.appendChild(h);
  col.appendChild(p);
  return col;
}

function _showToast(msg, type = 'info') {
  // Best-effort — use existing toast utility if present, else console
  if (typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else {
    console.warn(`[Toast ${type}] ${msg}`);
  }
}
