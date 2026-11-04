/**
 * memory-graph.js — Knowledge-graph view (entities + relationships).
 * Requirements: 9.2 (phase 2)
 *
 * Fetches /api/memory/graph/export and renders a lightweight SVG layout
 * (nodes placed on an ellipse, edges as lines) plus a plain entity list.
 * The force-layout viz from agent-graph.js is the richer precedent; this
 * view favours zero-dependency rendering with clear labels.
 */
import uiModule from './ui.js?v=20260916largetoolscroll1';

const GRAPH_API = '/api/memory/graph/export';

const TYPE_COLORS = {
  person: '#e06c75',
  project: '#61afef',
  concept: '#c678dd',
  tool: '#98c379',
  organisation: '#e5c07b',
};

export class MemoryGraphView {
  constructor() {
    this._overlay = null;
  }

  async open() {
    if (this._overlay) { this._overlay.remove(); this._overlay = null; }
    const overlay = document.createElement('div');
    overlay.className = 'modal p2-graph-modal';
    overlay.id = 'p2-graph-overlay';
    const content = document.createElement('div');
    content.className = 'modal-content';
    content.style.width = '720px';
    const header = document.createElement('div');
    header.className = 'modal-header';
    header.innerHTML = '<h4>Knowledge graph</h4>';
    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-btn';
    closeBtn.setAttribute('aria-label', 'Close knowledge graph');
    closeBtn.innerHTML = '&#x2716;';
    closeBtn.addEventListener('click', () => { overlay.remove(); if (this._overlay === overlay) this._overlay = null; });
    header.appendChild(closeBtn);
    content.appendChild(header);

    const body = document.createElement('div');
    body.className = 'modal-body';
    body.style.padding = '12px 16px';
    body.innerHTML = '<p class="p2-muted" style="color:color-mix(in srgb, var(--fg) 60%, transparent);font-size:0.85em;margin:0 0 10px;">Entities and relationships extracted from your conversations. Shown when the graph has data.</p>';
    const refreshBtn = document.createElement('button');
    refreshBtn.className = 'btn-secondary';
    refreshBtn.textContent = 'Refresh';
    refreshBtn.style.padding = '5px 12px';
    body.appendChild(refreshBtn);

    const svgBox = document.createElement('div');
    svgBox.style.cssText = 'margin-top:10px;border:1px solid var(--border);border-radius:8px;background:color-mix(in srgb, var(--bg) 85%, black);overflow:auto;';
    const listBox = document.createElement('div');
    listBox.style.cssText = 'margin-top:10px;max-height:220px;overflow-y:auto;';
    body.appendChild(svgBox);
    body.appendChild(listBox);
    content.appendChild(body);
    overlay.appendChild(content);
    document.body.appendChild(overlay);
    this._overlay = overlay;
    overlay.addEventListener('click', (ev) => { if (ev.target === overlay) overlay.remove(); });

    const load = async () => {
      svgBox.innerHTML = '<p style="padding:14px;color:color-mix(in srgb, var(--fg) 55%, transparent);">Loading…</p>';
      listBox.innerHTML = '';
      try {
        const res = await fetch(GRAPH_API, { headers: { 'Accept': 'application/json' } });
        if (!res.ok) throw new Error(`graph export failed: ${res.status}`);
        const data = await res.json();
        const nodes = Array.isArray(data.nodes) ? data.nodes : [];
        const edges = Array.isArray(data.edges) ? data.edges : [];
        if (!nodes.length) {
          svgBox.innerHTML = '<p style="padding:14px;color:color-mix(in srgb, var(--fg) 55%, transparent);">No entities yet — the graph grows as you chat (entities are extracted from assistant replies).</p>';
          return;
        }
        svgBox.innerHTML = '';
        svgBox.appendChild(this._renderSvg(nodes, edges));
        listBox.innerHTML = '';
        const esc = uiModule.esc;
        nodes.slice().sort((a, b) => (b.mention_count || 0) - (a.mention_count || 0)).forEach(n => {
          const row = document.createElement('div');
          row.style.cssText = 'padding:3px 4px;font-size:0.85em;border-bottom:1px solid color-mix(in srgb, var(--border) 50%, transparent);';
          const color = TYPE_COLORS[n.type] || '#abb2bf';
          row.innerHTML = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px;"></span><strong>${esc(n.name || '')}</strong>`
            + ` <span style="color:color-mix(in srgb, var(--fg) 50%, transparent);font-size:0.8em;">${esc(n.type || '')} · ${n.mention_count || 0} mention(s)</span>`;
          listBox.appendChild(row);
        });
      } catch (err) {
        console.warn('Memory graph load failed:', err);
        svgBox.innerHTML = '<p style="padding:14px;color:var(--red,#e06c75);">Could not load the knowledge graph.</p>';
      }
    };

    refreshBtn.addEventListener('click', load);
    await load();
  }

  _renderSvg(nodes, edges) {
    const esc = uiModule.esc;
    const W = 660, H = 360, cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 46;
    const byId = {};
    nodes.forEach((n, i) => {
      const ang = (i / Math.max(nodes.length, 1)) * 2 * Math.PI - Math.PI / 2;
      byId[n.id] = { x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang), node: n };
    });
    let edgeSvg = '';
    edges.forEach(e => {
      const s = byId[e.source], t = byId[e.target];
      if (!s || !t) return;
      edgeSvg += `<line x1="${s.x.toFixed(1)}" y1="${s.y.toFixed(1)}" x2="${t.x.toFixed(1)}" y2="${t.y.toFixed(1)}" stroke="color-mix(in srgb, var(--border) 80%, transparent)" stroke-width="1" />`;
    });
    let nodeSvg = '';
    nodes.forEach(n => {
      const p = byId[n.id];
      if (!p) return;
      const color = TYPE_COLORS[n.type] || '#abb2bf';
      const label = String(n.name || '').slice(0, 18);
      nodeSvg += `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="9" fill="${color}" opacity="0.9" />`
        + `<text x="${p.x.toFixed(1)}" y="${(p.y - 14).toFixed(1)}" text-anchor="middle" font-size="10" fill="color-mix(in srgb, var(--fg) 85%, transparent)">${esc(label)}</text>`;
    });
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.style.cssText = 'display:block;width:100%;height:auto;';
    svg.innerHTML = edgeSvg + nodeSvg;
    return svg;
  }
}

let _view = null;
export function getMemoryGraphView() {
  if (!_view) _view = new MemoryGraphView();
  return _view;
}

export async function openMemoryGraph() {
  await getMemoryGraphView().open();
}

export default MemoryGraphView;
