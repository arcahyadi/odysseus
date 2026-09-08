/**
 * fork-controls.js — "Fork from here" buttons on messages + source banner.
 * Requirements: 11.1, 11.2, 11.5, 11.7
 */

/**
 * Attach a "Fork from here" button to a regular chat message.
 * @param {HTMLElement} messageEl
 * @param {string} messageDbId - DB id of the message
 * @param {string} sessionId
 */
export function attachForkButtons(messageEl, messageDbId, sessionId) {
  if (!messageEl || !messageDbId || !sessionId) return;
  const btn = _makeForkButton();
  btn.addEventListener('click', async e => {
    e.stopPropagation();
    await _forkFromMessage(sessionId, messageDbId, null);
  });
  _appendToMessageActions(messageEl, btn);
}

/**
 * Attach a "Fork from here" button to a reasoning node element.
 * @param {HTMLElement} nodeEl
 * @param {string} nodeId - DB id of the ReasoningNode
 * @param {string} messageDbId - parent message DB id
 * @param {string} sessionId
 */
export function attachNodeForkButton(nodeEl, nodeId, messageDbId, sessionId) {
  if (!nodeEl || !nodeId || !messageDbId || !sessionId) return;
  const btn = _makeForkButton('Fork from this thought');
  btn.addEventListener('click', async e => {
    e.stopPropagation();
    await _forkFromMessage(sessionId, messageDbId, nodeId);
  });
  nodeEl.appendChild(btn);
}

/**
 * Fetch fork info and render a dismissible banner at the top of the session view.
 * @param {HTMLElement} sessionEl - container for the session/chat view
 * @param {string} sessionId
 */
export async function renderForkBanner(sessionEl, sessionId) {
  if (!sessionEl || !sessionId) return;
  try {
    const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/fork-info`);
    if (!res.ok) return;
    const info = await res.json();
    if (!info || !info.is_fork) return;
    _renderBanner(sessionEl, info);
  } catch (err) {
    console.warn('renderForkBanner failed:', err);
  }
}

// ── Internal ──────────────────────────────────────────────────────────────────

async function _forkFromMessage(sessionId, messageId, nodeId) {
  try {
    const body = { source_message_id: messageId };
    if (nodeId) body.source_node_id = nodeId;

    const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/fork`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Navigate to the new session (best-effort: fire a custom event)
    document.dispatchEvent(new CustomEvent('odysseus:fork-created', {
      bubbles: true,
      detail: { newSessionId: data.new_session_id, newSessionName: data.new_session_name },
    }));
  } catch (err) {
    console.warn('Fork failed:', err);
    if (typeof window.showToast === 'function') window.showToast('Fork failed', 'error');
  }
}

function _renderBanner(sessionEl, info) {
  // Remove existing banner if present
  const existing = sessionEl.querySelector('.fork-banner');
  if (existing) existing.remove();

  const banner = document.createElement('div');
  banner.className = 'fork-banner';
  banner.setAttribute('role', 'status');

  const msg = document.createElement('span');
  msg.textContent = 'Forked from ';

  const link = document.createElement('a');
  link.href = '#';
  link.textContent = info.source_session_name || info.source_session_id;
  link.addEventListener('click', e => {
    e.preventDefault();
    document.dispatchEvent(new CustomEvent('odysseus:open-session', {
      bubbles: true, detail: { sessionId: info.source_session_id },
    }));
  });

  const dismiss = document.createElement('button');
  dismiss.className = 'fork-banner__dismiss';
  dismiss.setAttribute('aria-label', 'Dismiss');
  dismiss.textContent = '✕';
  dismiss.addEventListener('click', () => banner.remove());

  msg.appendChild(link);
  banner.appendChild(msg);
  banner.appendChild(dismiss);
  sessionEl.insertBefore(banner, sessionEl.firstChild);
}

function _makeForkButton(label = 'Fork from here') {
  const btn = document.createElement('button');
  btn.className = 'fork-btn';
  btn.setAttribute('aria-label', label);
  btn.title = label;
  btn.textContent = '⑂';
  return btn;
}

function _appendToMessageActions(messageEl, btn) {
  let actions = messageEl.querySelector('.message-actions');
  if (!actions) {
    actions = document.createElement('div');
    actions.className = 'message-actions';
    messageEl.appendChild(actions);
  }
  actions.appendChild(btn);
}
