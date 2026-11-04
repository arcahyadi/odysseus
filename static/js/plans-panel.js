/**
 * plans-panel.js — Plans host panel: create from a document, list, execute,
 * pause, cancel. Embeds the phase-1 PlanTracker progress widget.
 * Requirements: 5.x UI (doc-to-action host)
 */
import uiModule from './ui.js?v=20260916largetoolscroll1';
import { PlanTracker } from './plan-tracker.js';
import { openDocStepBuilder } from './docStepBuilder.js';

const PLANS_API = '/api/plans';
const DOCS_API = '/api/documents/library';

export class PlansPanel {
  constructor() {
    this._overlay = null;
    this._pollers = [];
  }

  async open() {
    if (this._overlay) { this._overlay.remove(); this._overlay = null; }
    this._stopPollers();
    const overlay = document.createElement('div');
    overlay.className = 'modal p2-plans-modal';
    overlay.id = 'p2-plans-overlay';
    const content = document.createElement('div');
    content.className = 'modal-content';
    content.style.width = '700px';
    const header = document.createElement('div');
    header.className = 'modal-header';
    header.innerHTML = '<h4>Plans</h4>';
    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-btn';
    closeBtn.setAttribute('aria-label', 'Close plans panel');
    closeBtn.innerHTML = '&#x2716;';
    closeBtn.addEventListener('click', () => { overlay.remove(); if (this._overlay === overlay) this._overlay = null; this._stopPollers(); });
    header.appendChild(closeBtn);
    content.appendChild(header);

    const body = document.createElement('div');
    body.className = 'modal-body';
    body.style.padding = '12px 16px';

    // ── Create-from-document row ─────────────────────────────────────────
    const createRow = document.createElement('div');
    createRow.style.cssText = 'display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap;';
    const label = document.createElement('span');
    label.textContent = 'Turn a document into a plan:';
    label.style.cssText = 'font-size:0.85em;color:color-mix(in srgb, var(--fg) 75%, transparent);';
    createRow.appendChild(label);
    const docSel = document.createElement('select');
    docSel.id = 'p2-plan-doc-select';
    docSel.style.cssText = 'flex:1;min-width:180px;padding:5px 6px;';
    createRow.appendChild(docSel);
    const autoExec = document.createElement('label');
    autoExec.style.cssText = 'font-size:0.82em;display:flex;align-items:center;gap:4px;cursor:pointer;';
    autoExec.innerHTML = '<input type="checkbox" id="p2-plan-auto-exec" checked> auto-execute';
    createRow.appendChild(autoExec);
    const createBtn = document.createElement('button');
    createBtn.className = 'btn-primary';
    createBtn.textContent = 'Create plan';
    createBtn.style.padding = '6px 12px';
    createBtn.disabled = true;
    createRow.appendChild(createBtn);
    const createStatus = document.createElement('span');
    createStatus.style.cssText = 'font-size:0.82em;color:color-mix(in srgb, var(--fg) 60%, transparent);';
    createRow.appendChild(createStatus);
    body.appendChild(createRow);

    // ── Plans list ───────────────────────────────────────────────────────
    const listTitle = document.createElement('h5');
    listTitle.textContent = 'Your plans';
    listTitle.style.cssText = 'margin:6px 0 8px;font-size:0.95em;';
    body.appendChild(listTitle);
    const listBox = document.createElement('div');
    listBox.style.cssText = 'max-height:420px;overflow-y:auto;';
    body.appendChild(listBox);

    content.appendChild(body);
    overlay.appendChild(content);
    document.body.appendChild(overlay);
    this._overlay = overlay;
    overlay.addEventListener('click', (ev) => { if (ev.target === overlay) overlay.remove(); });

    // Load docs into the selector (library endpoint returns {documents}).
    const loadDocs = async () => {
      try {
        const res = await fetch(DOCS_API, { headers: { 'Accept': 'application/json' } });
        if (!res.ok) throw new Error(`documents library failed: ${res.status}`);
        const data = await res.json();
        const docs = (data && (data.documents || data.docs || [])) || [];
        docSel.innerHTML = '';
        if (!docs.length) {
          docSel.innerHTML = '<option value="">No documents found</option>';
          createBtn.disabled = true;
          return;
        }
        docs.forEach(d => {
          const opt = document.createElement('option');
          opt.value = d.id;
          opt.textContent = d.title || d.name || d.id;
          docSel.appendChild(opt);
        });
        createBtn.disabled = false;
      } catch (err) {
        console.warn('plans-panel docs load failed:', err);
        docSel.innerHTML = '<option value="">(documents unavailable)</option>';
        createBtn.disabled = true;
      }
    };

    const renderList = async () => {
      listBox.innerHTML = '<p style="color:color-mix(in srgb, var(--fg) 55%, transparent);">Loading…</p>';
      try {
        const res = await fetch(PLANS_API, { headers: { 'Accept': 'application/json' } });
        if (!res.ok) throw new Error(`plans list failed: ${res.status}`);
        const plans = await res.json();
        listBox.innerHTML = '';
        if (!Array.isArray(plans) || !plans.length) {
          listBox.innerHTML = '<p style="color:color-mix(in srgb, var(--fg) 55%, transparent);">No plans yet — pick a document above and press "Create plan".</p>';
          return;
        }
        plans.forEach(plan => {
          const row = document.createElement('div');
          row.className = 'p2-plan-row';
          row.style.cssText = 'border:1px solid var(--border);border-radius:8px;padding:8px 10px;margin-bottom:8px;';
          const top = document.createElement('div');
          top.style.cssText = 'display:flex;align-items:center;gap:8px;flex-wrap:wrap;';
          const name = document.createElement('strong');
          name.textContent = plan.title || plan.goal || plan.id;
          name.style.cssText = 'flex:1;min-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
          top.appendChild(name);
          const badge = document.createElement('span');
          badge.className = 'p2-plan-status';
          badge.textContent = plan.status || '';
          top.appendChild(badge);
          ['execute', 'pause', 'cancel', 'delete'].forEach(act => {
            const btn = document.createElement('button');
            btn.className = 'btn-secondary';
            btn.textContent = act;
            btn.style.cssText = 'padding:3px 10px;font-size:0.78em;';
            btn.addEventListener('click', async () => {
              try {
                const r = await fetch(`${PLANS_API}/${encodeURIComponent(plan.id)}/${act}`, { method: act === 'execute' ? 'POST' : 'POST' });
                if (!r.ok && r.status !== 404) throw new Error(`${act} failed: ${r.status}`);
              } catch (err) {
                uiModule.showError(err.message);
              } finally {
                renderList();
                loadDocs();
              }
            });
            top.appendChild(btn);
          });
          // Add document step button
          const addStepBtn = document.createElement('button');
          addStepBtn.className = 'btn-secondary';
          addStepBtn.textContent = 'Add step';
          addStepBtn.style.cssText = 'padding:3px 10px;font-size:0.78em;';
          addStepBtn.addEventListener('click', () => {
            openDocStepBuilder(plan.id, plan.title || plan.goal || plan.id);
          });
          top.appendChild(addStepBtn);
          row.appendChild(top);
          // PlanTracker progress widget (phase 1) — polls while active.
          const progHost = document.createElement('div');
          progHost.style.cssText = 'margin-top:6px;';
          row.appendChild(progHost);
          if (plan.id) {
            const tracker = new PlanTracker(plan.id, progHost);
            tracker.refresh();
            if (plan.status === 'running') {
              tracker.startPolling(2500);
              this._pollers.push(tracker);
            }
          }
          listBox.appendChild(row);
        });
      } catch (err) {
        listBox.innerHTML = '<p style="color:var(--red,#e06c75);">Could not load plans.</p>';
      }
    };

    createBtn.addEventListener('click', async () => {
      const documentId = docSel.value;
      if (!documentId) return;
      createBtn.disabled = true;
      createStatus.textContent = 'Creating…';
      try {
        const res = await fetch(`${PLANS_API}/from-document`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ document_id: documentId, auto_execute: autoExec.querySelector('input').checked }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          createStatus.textContent = (data && data.detail) ? String(data.detail) : `Failed (${res.status})`;
          uiModule.showError(createStatus.textContent);
          return;
        }
        createStatus.textContent = data.auto_executed ? 'Plan created — execution started.' : 'Plan created.';
        renderList();
      } catch (err) {
        createStatus.textContent = 'Create failed.';
        uiModule.showError('Plan creation failed: ' + err.message);
      } finally {
        setTimeout(() => { createBtn.disabled = false; }, 1200);
      }
    });

    await loadDocs();
    await renderList();
  }

  _stopPollers() {
    this._pollers.forEach(p => p.stopPolling());
    this._pollers = [];
  }
}

let _panel = null;
export function getPlansPanel() {
  if (!_panel) _panel = new PlansPanel();
  return _panel;
}

export async function openPlansPanel() {
  await getPlansPanel().open();
}

export default PlansPanel;
