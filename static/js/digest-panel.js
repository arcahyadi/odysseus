/**
 * digest-panel.js — Morning Digest / auto-digest panel.
 * Requirements: 9.3 (phase 2)
 *
 * Consumes the /api/digest API (list, generate, search). Shows today's
 * briefing (narrative + calendar/email/todos data when present) and the
 * recent digest history, with on-demand regeneration.
 */
import uiModule from './ui.js?v=20260916largetoolscroll1';

const API_BASE = '/api/digest';

export class DigestPanel {
  constructor() {
    this._overlay = null;
    this._busy = false;
  }

  async open() {
    if (this._overlay) { this._overlay.remove(); this._overlay = null; }
    const overlay = document.createElement('div');
    overlay.className = 'modal p2-digest-modal';
    overlay.id = 'p2-digest-overlay';
    const content = document.createElement('div');
    content.className = 'modal-content';
    content.style.width = '640px';
    const header = document.createElement('div');
    header.className = 'modal-header';
    header.innerHTML = '<h4>Morning Digest</h4>';
    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-btn';
    closeBtn.setAttribute('aria-label', 'Close digest panel');
    closeBtn.innerHTML = '&#x2716;';
    closeBtn.addEventListener('click', () => { overlay.remove(); if (this._overlay === overlay) this._overlay = null; });
    header.appendChild(closeBtn);
    content.appendChild(header);

    const body = document.createElement('div');
    body.className = 'modal-body';
    body.style.padding = '12px 16px';
    body.innerHTML = '<p class="p2-muted" style="color:color-mix(in srgb, var(--fg) 60%, transparent);font-size:0.85em;margin:0 0 10px;">Daily briefing: today\'s calendar, unread email highlights and open todos — generated on demand or on a schedule (Tasks → Morning Digest).</p>';
    const actions = document.createElement('div');
    actions.style.cssText = 'display:flex;gap:8px;align-items:center;margin-bottom:12px;';
    const genBtn = document.createElement('button');
    genBtn.className = 'btn-primary';
    genBtn.textContent = 'Generate now';
    genBtn.style.padding = '6px 14px';
    actions.appendChild(genBtn);
    const status = document.createElement('span');
    status.className = 'p2-digest-status';
    status.style.cssText = 'font-size:0.85em;color:color-mix(in srgb, var(--fg) 65%, transparent);';
    actions.appendChild(status);
    body.appendChild(actions);

    const todayBox = document.createElement('div');
    todayBox.className = 'p2-digest-today';
    body.appendChild(todayBox);
    const historyTitle = document.createElement('h5');
    historyTitle.textContent = 'Recent digests';
    historyTitle.style.cssText = 'margin:16px 0 6px;font-size:0.95em;';
    body.appendChild(historyTitle);
    const searchRow = document.createElement('div');
    searchRow.style.cssText = 'margin-bottom:8px;display:flex;gap:6px;';
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Search digests…';
    searchInput.style.cssText = 'flex:1;padding:5px 8px;';
    searchRow.appendChild(searchInput);
    body.appendChild(searchRow);
    const historyBox = document.createElement('div');
    historyBox.style.cssText = 'max-height:320px;overflow-y:auto;';
    body.appendChild(historyBox);

    content.appendChild(body);
    overlay.appendChild(content);
    document.body.appendChild(overlay);
    this._overlay = overlay;
    overlay.addEventListener('click', (ev) => { if (ev.target === overlay) overlay.remove(); });

    const render = async (q) => {
      todayBox.innerHTML = '<p class="p2-muted">Loading…</p>';
      try {
        const url = q ? `${API_BASE}/search?q=${encodeURIComponent(q)}` : `${API_BASE}/`;
        const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
        if (!res.ok) throw new Error(`digest list failed: ${res.status}`);
        const data = await res.json();
        const digests = (data && data.digests) ? data.digests : [];
        if (q) {
          historyBox.innerHTML = digests.length ? '' : '<p class="p2-muted">No digests match.</p>';
          digests.forEach(d => historyBox.appendChild(this._renderHistoryRow(d)));
          return;
        }
        const todayStr = new Date().toISOString().slice(0, 10);
        const today = digests.find(d => d.date === todayStr) || null;
        todayBox.innerHTML = '';
        if (today) todayBox.appendChild(this._renderToday(today));
        else todayBox.innerHTML = '<p class="p2-muted">No briefing for today yet — press "Generate now".</p>';
        historyBox.innerHTML = '';
        if (!digests.length) historyBox.innerHTML = '<p class="p2-muted">No digests yet.</p>';
        digests.slice(0, 20).forEach(d => historyBox.appendChild(this._renderHistoryRow(d)));
      } catch (err) {
        console.warn('Digest panel load failed:', err);
        todayBox.innerHTML = '<p class="p2-muted">Could not load digests.</p>';
      }
    };

    genBtn.addEventListener('click', async () => {
      if (this._busy) return;
      this._busy = true;
      genBtn.disabled = true;
      status.textContent = 'Generating…';
      try {
        const res = await fetch(`${API_BASE}/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        });
        if (!res.ok) throw new Error(`generate failed: ${res.status}`);
        status.textContent = 'Queued — this can take a minute.';
        setTimeout(() => render(''), 4000);
      } catch (err) {
        status.textContent = 'Generation failed.';
        uiModule.showError('Digest generation failed: ' + err.message);
      } finally {
        this._busy = false;
        setTimeout(() => { genBtn.disabled = false; }, 1500);
      }
    });

    let searchTimer = null;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      const q = searchInput.value.trim();
      searchTimer = setTimeout(() => render(q), 350);
    });

    await render('');
  }

  _renderToday(d) {
    const wrap = document.createElement('div');
    wrap.className = 'p2-digest-card';
    wrap.style.cssText = 'border:1px solid var(--border);border-radius:8px;padding:10px 12px;';
    const esc = uiModule.esc;
    let narrative = '';
    const content = d.content && typeof d.content === 'object' ? d.content : {};
    if (content.narrative) narrative = String(content.narrative);
    else if (typeof d.summary === 'string') narrative = d.summary;
    else if (typeof content === 'string') narrative = content;
    const meta = [];
    if (Array.isArray(content.calendar) && content.calendar.length) meta.push(`${content.calendar.length} calendar event(s)`);
    if (content.email && content.email.unread != null) meta.push(`${content.email.unread} unread`);
    if (Array.isArray(content.todos) && content.todos.length) meta.push(`${content.todos.length} open todo(s)`);
    const head = document.createElement('div');
    head.innerHTML = `<strong>Today · ${esc(d.date || '')}</strong> ${d.status === 'failed' ? '<span style="color:var(--red,#e06c75)">failed</span>' : ''}${meta.length ? ` <span style="color:color-mix(in srgb, var(--fg) 55%, transparent);font-size:0.8em;">(${esc(meta.join(', '))})</span>` : ''}`;
    wrap.appendChild(head);
    const text = document.createElement('div');
    text.style.cssText = 'white-space:pre-wrap;margin-top:6px;font-size:0.92em;line-height:1.5;';
    text.textContent = narrative || '(no narrative)';
    wrap.appendChild(text);
    return wrap;
  }

  _renderHistoryRow(d) {
    const esc = uiModule.esc;
    const row = document.createElement('div');
    row.style.cssText = 'border-bottom:1px solid color-mix(in srgb, var(--border) 60%, transparent);padding:6px 2px;';
    const summary = (typeof d.summary === 'string' && d.summary) ? d.summary : ((d.content && typeof d.content === 'object' && d.content.narrative) ? d.content.narrative : '');
    row.innerHTML = `<details><summary style="cursor:pointer;"><strong>${esc(d.date || '')}</strong> <span style="color:color-mix(in srgb, var(--fg) 55%, transparent);font-size:0.8em;">${esc(d.status || '')}</span><span style="color:color-mix(in srgb, var(--fg) 70%, transparent);font-size:0.85em;">${esc(summary ? ' · ' + summary.slice(0, 120) : '')}</span></summary>`
      + `<div style="white-space:pre-wrap;font-size:0.88em;margin:4px 2px 2px;">${esc(summary || '(no summary)')}</div></details>`;
    return row;
  }
}

let _panel = null;
export function getDigestPanel() {
  if (!_panel) _panel = new DigestPanel();
  return _panel;
}

export async function openDigestPanel() {
  await getDigestPanel().open();
}

export default DigestPanel;
