# Odysseus Clipper (browser extension)

A Manifest V3 extension that sends selected text or whole pages to your
Odysseus server as a **note**, **document**, **memory**, or **chat message**.

> Status: skeleton. The endpoints below are the create routes verified in this
> repo (2026-09); the chat payload body should be re-verified against your
> running build. Icons referenced in `manifest.json` (`icons/icon*.png`) are
> not bundled — copy any 16/48/128px PNGs (e.g. from `static/icons/` if they
> fit, or export the wordmark) into `extension/icons/` before loading.

## Install (unpacked)

1. Open `chrome://extensions`, enable **Developer mode**.
2. **Load unpacked** → choose this `extension/` folder.
3. Open the popup and set:
   - **Server URL** — e.g. `http://localhost:8090` (no trailing slash).
   - **API token** — create one in Odysseus *Settings → API Tokens* (`ody_…`);
     the extension sends `Authorization: Bearer ody_…`. If the server runs
     without auth enabled, the token can be left blank.

## Use

- Select text on any page → right-click → **Send selection to Odysseus**.
- Or open the popup, choose *Page selection* / *Whole page*, edit the text,
  pick the target (**Note / Document / Memory / Chat message**), and press
  **Send**.

## How it talks to Odysseus

| Target | Request |
| ------ | ------- |
| Note | `POST {origin}/api/notes` `{title, content, note_type: "note"}` |
| Memory | `POST {origin}/api/memory` `{text, source: "clipper"}` |
| Document | `POST {origin}/api/document` `{title, content}` |
| Chat | `POST {origin}/api/chat` `{message, session}` — requires an existing chat session id (the popup shows a *Session id* field when Chat is selected) |

Auth: `Authorization: Bearer <ody_…>` (see `src/auth_helpers.py`). The LAN
pairing flow in `companion/` is the alternative for token discovery: run the
companion CLI to mint a token for this machine instead of pasting one.

## Layout

- `manifest.json` — MV3 manifest (context menus, storage, notifications).
- `background.js` — context-menu handler + `sendToOdysseus()` fetch logic.
- `content.js` — captures selection or page text on demand.
- `popup.html/js/css` — configuration + manual send.
