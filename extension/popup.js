/**
 * Odysseus Clipper — popup controller.
 * Saves server/token to chrome.storage.sync and dispatches clipper sends.
 */
const $ = (sel) => document.querySelector(sel);

document.addEventListener('DOMContentLoaded', async () => {
  const cfg = await chrome.storage.sync.get(['serverOrigin', 'token', 'type', 'mode']);
  $('#server').value = cfg.serverOrigin || '';
  $('#token').value = cfg.token || '';
  $('#type').value = cfg.type || 'note';
  $('#mode').value = cfg.mode || 'selection';
});

$('#server').addEventListener('change', persist);
$('#token').addEventListener('change', persist);
$('#type').addEventListener('change', onTypeChange);
$('#mode').addEventListener('change', onModeChange);
$('#session').addEventListener('change', persist);

function onTypeChange() {
  const isChat = $('#type').value === 'chat';
  $('#session-label').hidden = !isChat;
  $('#session').hidden = !isChat;
  persist();
}

async function persist() {
  await chrome.storage.sync.set({
    serverOrigin: $('#server').value.trim(),
    token: $('#token').value.trim(),
    type: $('#type').value,
    mode: $('#mode').value,
  });
}

async function onModeChange() {
  await persist();
  await loadCapture();
}

async function loadCapture() {
  const mode = $('#mode').value;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || tab.id === undefined) return;
    const resp = await chrome.tabs.sendMessage(tab.id, { kind: 'odysseus.clipper.capture', mode });
    if (resp && resp.text) {
      $('#text').value = resp.text;
      if (mode === 'selection' && !resp.text && window.getSelection && document.activeElement) {
        // Fallback: selection lives in the page, not the popup.
      }
    }
  } catch (e) {
    // Content script not injected on this page (e.g. chrome:// pages).
    $('#text').placeholder = 'Capture unavailable on this page — paste text manually.';
  }
}

$('#send').addEventListener('click', async () => {
  await persist();
  const status = $('#status');
  status.textContent = 'Sending…';
  const text = $('#text').value.trim();
  if (!text) {
    status.textContent = 'Nothing to send.';
    return;
  }
  const payload = {
    kind: 'odysseus.clipper.send',
    payload: { type: $('#type').value, title: '', text, sessionId: $('#session').value.trim() },
  };
  try {
    const resp = await chrome.runtime.sendMessage(payload);
    if (resp && resp.ok) {
      status.textContent = 'Sent ✓';
    } else {
      status.textContent = 'Failed: ' + (resp && resp.error || 'unknown error');
    }
  } catch (err) {
    status.textContent = 'Failed: ' + err.message;
  }
});

// Load current capture when the popup opens.
loadCapture();
