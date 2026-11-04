/**
 * reasoning-trace.js — Collapsible <think> trace display in chat messages.
 * Requirements: 10.1, 10.2, 10.3, 10.6, 10.7
 */

/**
 * Fetch and attach a reasoning trace to a rendered message element.
 * @param {HTMLElement} messageEl - the rendered message container
 * @param {string} messageDbId - the DB id of the assistant message
 */
export async function attachReasoningTrace(messageEl, messageDbId) {
  if (!messageEl || !messageDbId) return;
  try {
    const res = await fetch(`/api/reasoning/by-message/${encodeURIComponent(messageDbId)}`);
    if (!res.ok) return;
    const data = await res.json();
    const trace = data && data.id ? data : (data && data.trace ? data.trace : null);
    if (!trace || !Array.isArray(trace.nodes) || trace.nodes.length === 0) return;
    _renderTrace(messageEl, trace.nodes);
  } catch (err) {
    console.warn('attachReasoningTrace failed:', err);
  }
}

/**
 * Append a streaming reasoning node to an open trace container.
 * Called during active SSE streaming when a thinking_node event arrives.
 * @param {HTMLElement} traceContainer - the <details> element
 * @param {string} nodeContent - text content of the node
 * @param {number} index - sequential node index
 */
export function appendStreamingNode(traceContainer, nodeContent, index) {
  if (!traceContainer) return;
  const div = document.createElement('div');
  div.className = 'reasoning-node reasoning-node--streaming';
  div.dataset.index = index;
  div.dataset.chars = (nodeContent || '').length;
  div.title = `Step ${index + 1} · ${(nodeContent || '').length} chars`;
  div.textContent = nodeContent || '';
  traceContainer.appendChild(div);
}

/**
 * Create or get the streaming trace container for an in-progress message.
 * @param {HTMLElement} messageEl
 * @returns {HTMLElement} the <details> element
 */
export function ensureStreamingTraceContainer(messageEl) {
  let details = messageEl.querySelector('.reasoning-trace');
  if (details) return details;
  details = _makeDetailsEl(0);
  messageEl.insertBefore(details, messageEl.firstChild);
  return details;
}

// ── Internal ──────────────────────────────────────────────────────────────────

function _renderTrace(messageEl, nodes) {
  // Remove any pre-existing trace (e.g. streaming placeholder)
  const existing = messageEl.querySelector('.reasoning-trace');
  if (existing) existing.remove();

  const details = _makeDetailsEl(nodes.length);
  const sorted = [...nodes].sort((a, b) => a.index - b.index);
  sorted.forEach(node => {
    const div = document.createElement('div');
    div.className = 'reasoning-node';
    div.dataset.index = node.index;
    div.dataset.chars = (node.content || '').length;
    div.title = `Step ${node.index + 1} · ${(node.content || '').length} chars`;
    div.textContent = node.content || '';
    details.appendChild(div);
  });

  messageEl.insertBefore(details, messageEl.firstChild);
}

function _makeDetailsEl(nodeCount) {
  const details = document.createElement('details');
  details.className = 'reasoning-trace';
  const summary = document.createElement('summary');
  summary.className = 'reasoning-trace__summary';
  summary.textContent = nodeCount > 0
    ? `🤔 Thinking (${nodeCount} step${nodeCount === 1 ? '' : 's'})`
    : '🤔 Thinking…';
  details.appendChild(summary);
  return details;
}
