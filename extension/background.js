/**
 * Odysseus Clipper — background service worker.
 *
 * - Registers the "Send selection to Odysseus" context menu on text selections.
 * - Stores server origin + bearer token (ody_...) via chrome.storage.sync.
 * - Sends payloads to the configured server with `Authorization: Bearer <ody_...>`.
 *
 * Target endpoints (verified against routes in this repo at build time):
 *   note     -> POST {origin}/api/notes     {title, content, note_type: "note"}
 *   memory   -> POST {origin}/api/memory    {text, source: "clipper"}
 *   document -> POST {origin}/api/document  {title, content}
 *   chat     -> POST {origin}/api/chat      {message, session}  (existing session id)
 */
const TARGET_ENDPOINTS = {
  note: '/api/notes',
  memory: '/api/memory',
  document: '/api/document',
  chat: '/api/chat',
};

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'odysseus-send-selection',
    title: 'Send selection to Odysseus',
    contexts: ['selection'],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== 'odysseus-send-selection') return;
  if (!info.selectionText) return;
  sendToOdysseus({ type: 'note', title: pageTitle(tab), text: info.selectionText })
    .then((r) => notify(r))
    .catch((err) => notify({ ok: false, error: String(err && err.message || err) }));
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.kind !== 'odysseus.clipper.send') return;
  sendToOdysseus(msg.payload)
    .then((r) => sendResponse(r))
    .catch((err) => sendResponse({ ok: false, error: String(err && err.message || err) }));
  return true; // async response
});

async function getConfig() {
  const cfg = await chrome.storage.sync.get(['serverOrigin', 'token']);
  const origin = String(cfg.serverOrigin || '').trim().replace(/\/+$/, '');
  const token = String(cfg.token || '').trim();
  if (!origin) throw new Error('Server URL not set — open the popup and configure it.');
  if (!/^https?:\/\//.test(origin)) throw new Error('Server URL must start with http(s)://');
  return { origin, token };
}

function pageTitle(tab) {
  return (tab && tab.title) || document.title || '';
}

async function sendToOdysseus({ type, title, text, pageUrl, sessionId }) {
  const { origin, token } = await getConfig();
  const endpoint = TARGET_ENDPOINTS[type];
  if (!endpoint) throw new Error('Unknown target type: ' + type);
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = 'Bearer ' + token;

  let body;
  if (type === 'note') {
    body = JSON.stringify({ title: title || 'Clipped', content: text, note_type: 'note', source: 'clipper' });
  } else if (type === 'memory') {
    body = JSON.stringify({ text: text, source: 'clipper', category: 'fact' });
  } else if (type === 'document') {
    body = JSON.stringify({ title: title || 'Clipped page', content: text });
  } else {
    // Chat requires an existing session id (chat_routes ChatRequest).
    body = JSON.stringify({ message: text, session: sessionId || '' });
  }

  const res = await fetch(origin + endpoint, { method: 'POST', headers, body });
  if (!res.ok) {
    throw new Error('Server responded ' + res.status + ' for ' + endpoint);
  }
  const data = await res.json().catch(() => ({}));
  return { ok: true, status: res.status, type, data, pageUrl };
}

function notify(r) {
  if (!r.ok) {
    chrome.notifications?.create('odysseus-clipper-error', {
      type: 'basic', iconUrl: 'icons/icon48.png', title: 'Odysseus Clipper',
      message: 'Send failed: ' + (r.error || 'unknown error'),
    });
    return;
  }
  chrome.notifications?.create('odysseus-clipper-ok', {
    type: 'basic', iconUrl: 'icons/icon48.png', title: 'Odysseus Clipper',
    message: 'Sent to ' + r.type + '.',
  });
}

// Exported for tests/other entry points.
if (typeof module !== 'undefined') module.exports = { sendToOdysseus, getConfig, TARGET_ENDPOINTS };
