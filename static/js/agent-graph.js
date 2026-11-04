/**
 * agent-graph.js — SVG DAG visualisation of multi-agent runs.
 * Requirements: 2.2, 2.6, 2.7, 2.8
 */

const NODE_W = 160, NODE_H = 72, GAP_X = 32, GAP_Y = 48, PAD = 20;

const STATUS_COLOUR = {
  pending:   '#94a3b8',
  running:   '#3b82f6',
  completed: '#22c55e',
  failed:    '#ef4444',
  paused:    '#f59e0b',
  cancelled: '#6b7280',
};

export class AgentGraph {
  /**
   * @param {HTMLElement} container - will receive a <svg> child
   */
  constructor(container) {
    this.container = container;
    this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    this.svg.setAttribute('class', 'agent-graph');
    this.svg.setAttribute('role', 'img');
    this.svg.setAttribute('aria-label', 'Agent execution graph');
    container.appendChild(this.svg);
    this._evtSource = null;
    this._nodes = new Map(); // run_id → {x, y, data}
  }

  /** Connect to the SSE stream for rootRunId. */
  connect(rootRunId) {
    this.disconnect();
    this._evtSource = new EventSource(`/api/agents/runs/${encodeURIComponent(rootRunId)}/stream`);
    this._evtSource.addEventListener('agent_graph_snapshot', e => {
      try { this._renderSnapshot(JSON.parse(e.data)); } catch (_) {}
    });
    this._evtSource.addEventListener('agent_run_event', e => {
      try { this._handleRunEvent(JSON.parse(e.data)); } catch (_) {}
    });
    this._evtSource.onerror = () => {
      console.warn('AgentGraph SSE error for run', rootRunId);
    };
  }

  /** Close the SSE stream. */
  disconnect() {
    if (this._evtSource) { this._evtSource.close(); this._evtSource = null; }
  }

  // ── Rendering ──────────────────────────────────────────────────────────────

  _renderSnapshot({ nodes }) {
    if (!Array.isArray(nodes) || nodes.length === 0) return;
    this.svg.innerHTML = '';
    this._nodes.clear();

    // Group by depth for layered layout
    const layers = {};
    nodes.forEach(n => {
      const d = n.depth ?? 0;
      (layers[d] = layers[d] || []).push(n);
    });

    // Assign positions
    const positions = {};
    Object.entries(layers).forEach(([depthStr, layerNodes]) => {
      const depth = Number(depthStr);
      layerNodes.forEach((n, i) => {
        positions[n.id] = {
          x: PAD + i * (NODE_W + GAP_X),
          y: PAD + depth * (NODE_H + GAP_Y),
        };
      });
    });

    // Draw edges first (behind nodes)
    nodes.forEach(n => {
      if (n.parent_run_id && positions[n.parent_run_id] && positions[n.id]) {
        this._drawEdge(positions[n.parent_run_id], positions[n.id]);
      }
    });

    // Draw nodes
    nodes.forEach(n => {
      const pos = positions[n.id];
      if (pos) {
        this._drawNode(n, pos.x, pos.y);
        this._nodes.set(n.id, { x: pos.x, y: pos.y, data: n });
      }
    });

    // Update SVG size to fit content
    const maxX = Math.max(...Object.values(positions).map(p => p.x)) + NODE_W + PAD;
    const maxY = Math.max(...Object.values(positions).map(p => p.y)) + NODE_H + PAD;
    this.svg.setAttribute('width', maxX);
    this.svg.setAttribute('height', maxY);
    this.svg.setAttribute('viewBox', `0 0 ${maxX} ${maxY}`);
  }

  _handleRunEvent(evt) {
    const nodeEntry = this._nodes.get(evt.run_id);
    if (!nodeEntry) return;
    nodeEntry.data.status = evt.status;
    // Re-colour the node rect in-place
    const rect = this.svg.querySelector(`[data-run-id="${CSS.escape(evt.run_id)}"] rect`);
    if (rect) rect.setAttribute('fill', STATUS_COLOUR[evt.status] || STATUS_COLOUR.pending);
  }

  _drawNode(n, x, y) {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('class', `agent-node agent-node--${n.status}`);
    g.setAttribute('data-run-id', n.id);
    g.setAttribute('aria-label', n.task_description || n.id);
    g.setAttribute('tabindex', '0');

    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('x', x); rect.setAttribute('y', y);
    rect.setAttribute('width', NODE_W); rect.setAttribute('height', NODE_H);
    rect.setAttribute('rx', '6');
    rect.setAttribute('fill', STATUS_COLOUR[n.status] || STATUS_COLOUR.pending);
    rect.setAttribute('stroke', '#1e293b'); rect.setAttribute('stroke-width', '1.5');

    const label = (n.task_description || n.id).slice(0, 28);
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', x + NODE_W / 2); text.setAttribute('y', y + NODE_H / 2 - 8);
    text.setAttribute('text-anchor', 'middle'); text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('fill', '#fff'); text.setAttribute('font-size', '11');
    text.textContent = label + (label.length < (n.task_description || '').length ? '…' : '');

    const statusText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    statusText.setAttribute('x', x + NODE_W / 2); statusText.setAttribute('y', y + NODE_H / 2 + 14);
    statusText.setAttribute('text-anchor', 'middle'); statusText.setAttribute('fill', '#e2e8f0');
    statusText.setAttribute('font-size', '10');
    statusText.textContent = n.status || '';

    g.appendChild(rect); g.appendChild(text); g.appendChild(statusText);
    g.addEventListener('click', () => this._onNodeClick(n));
    g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') this._onNodeClick(n); });
    this.svg.appendChild(g);
  }

  _drawEdge(from, to) {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', from.x + NODE_W / 2); line.setAttribute('y1', from.y + NODE_H);
    line.setAttribute('x2', to.x + NODE_W / 2);   line.setAttribute('y2', to.y);
    line.setAttribute('stroke', '#64748b'); line.setAttribute('stroke-width', '1.5');
    line.setAttribute('stroke-dasharray', '4 2');
    this.svg.insertBefore(line, this.svg.firstChild);
  }

  _onNodeClick(nodeData) {
    this.container.dispatchEvent(new CustomEvent('agent-node-click', {
      bubbles: true, detail: nodeData,
    }));
  }
}
