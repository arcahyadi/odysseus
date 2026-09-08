// Odysseus Clipper — content script: no DOM writes; grabs selection/page text
// on demand via message from the popup or background (context menu flow uses
// info.selectionText directly, so this file is mostly a hook for page-level
// capture when the user asks for the whole page).
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.kind !== 'odysseus.clipper.capture') return;
  let text = '';
  if (msg.mode === 'selection') {
    const sel = window.getSelection();
    text = sel ? sel.toString() : '';
  } else {
    text = (document.body && document.body.innerText) ? document.body.innerText.slice(0, 20000) : '';
  }
  sendResponse({ text: text || '', title: document.title || '', url: location.href });
  return true;
});
