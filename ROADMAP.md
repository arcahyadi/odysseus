# Roadmap / Help Wanted

Odysseus is on a voyage, but not home yet. It works great for me (lol), but this ship is moving fast and feedback/help would be appreciated! (I don't know what I'm doing, help).

If you see weird CSS, strange layout behavior, or a suspiciously murky corner of
the codebase, you are probably right to stay away.

## In Progress — current build iteration (2026-09)

Tracked in the project task board. Phase 1 (intelligence/reasoning) and Phase 2
(knowledge/memory: digest, knowledge graph, citations, temporal memory) are
complete: both spec boards are fully ticked and `tests/phase2` passes. The Phase 2
end-to-end checkpoint (`.kiro/specs/phase-2-knowledge-memory/tasks.md` L204)
passed on 2026-09-13, after fixing two defects it uncovered — an unreachable
`GET /api/memory/time-range` (shadowed by the `/{memory_id}` wildcard) and a
`POST /api/digest/generate` that resolved no default endpoint and so always
persisted a failed digest.

Built (2026-09): **#8 Shared workspaces MVP** — read-only session share tokens
(`/api/share/sessions` CRUD, owner-scoped) + public replay/live SSE streams
(`/api/s/{token}/stream`) with a live broadcast hook on assistant-message
persist. **Local mobile app (replaces #10)** — Expo scaffold in `mobile/`
(Pairing, Chat w/ SSE, Memory, Digest, Notes, Plans, Home) for LAN use.
Built (2026-09): **Email automation rules (#6)** — rule engine, CRUD/evaluate/
execute API (`/api/email-rules`), `create_task` → checklist Note, and a
deduped trigger hook in the email poll pass (`routes/email_pollers.py`).
**Browser extension / web clipper (#4)** — MV3 extension in `extension/`
sending selection/page to note / document / memory / chat (chat requires an
existing session id) via Bearer `ody_…` tokens.

Still open from the earlier gap analysis: the plugin marketplace idea was
replaced by the local mobile app (see above); ROADMAP items below remain.

## High Priority

- SQUASH BUGS
- Fresh install smoke tests on Linux, macOS, and Windows. Docker, native Python,
  and WSL all need coverage.

- Integration audit: do integrations even work? Confirm what works, what needs setup docs, and what should be removed or hidden. 
- Self-host troubleshooting cookbook. Document the weird 30-second fixes that otherwise become 30-minute searches: Dovecot cleartext auth for local stacks, ntfy Android Instant Delivery for non-ntfy.sh servers, clipboard limits on plain-HTTP Tailscale URLs, Radicale collection URLs, and similar traps.
- Cookbook reliability on other computers. This is probably the area most likely to need work across different machines, GPUs, drivers, shells, and Python environments.
- Cookbook SGLang support across platforms. Make sure SGLang setup/serve works
  predictably on Linux, Windows/WSL, macOS where possible, Docker, and common
  NVIDIA/AMD hardware paths.
- Deep Research model presets by hardware. Recommend approved model/parameter
  profiles for small, medium, and large local setups so people with different
  hardware can use Deep Research without guessing. Surface this either in Deep
  Research settings or as a Cookbook scan/dropdown suggestion.
- Cookbook model scan/download ranking. Prioritize newer architectures and
  better hardware-fit models instead of scoring everything almost the same.
  Ranking should account for architecture age, quant format, VRAM/RAM fit,
  backend support, vision/mmproj requirements, and likely serve reliability.
- Cookbook error feedback and logging. Failed downloads, dependency installs,
  preflights, and serve jobs should show the actual command/output/error in the
  UI, with copyable logs and clear next steps instead of just "crashed".
- Agent prompt/context bloat. Agent mode is too heavy for smaller local models:
  tool schemas, skills, memory, documents, and instructions can eat the context
  before the user request really starts. We need slimmer prompts, better tool
  selection, smaller default tool sets, and clearer guidance for models with
  4k/8k/16k context windows.
- Skill/tool prompt-injection audit. User-editable skills, notes, documents,
  fetched pages, and memories should be treated as untrusted data. Keep testing
  whether models follow malicious instructions from those surfaces.
- Better degraded-state reporting for ChromaDB, SearXNG, email, ntfy, and provider probes.
- Email performance audit. Fetching, searching, opening, deleting, and sending
  email can feel slow, especially over IMAP/SMTP providers with high latency.
  Need someone who knows mail performance to profile the current flow, identify
  whether the bottleneck is IMAP folder select/fetch, cache invalidation,
  attachment/body loading, SMTP handshakes, or frontend refresh behavior, then
  propose safer caching/prefetch/batching without breaking multi-account state.
- Provider setup/probing audit for Anthropic, Gemini, Groq, xAI, OpenRouter, OpenAI, and DeepSeek.

## Refactor Targets
- CSS cleanup. `static/style.css` basically Calypso's island atm.
- Tour core helper. The onboarding tours have too much copy-pasted scaffolding; promote a shared `tour-core.js` helper before adding more tours.
- Modal/window positioning cleanup. Some window controls have improved, but the
  underlying popup/dropdown/fixed-position behavior is still too fragile.
- Mobile media override discoverability. A lot of "CSS did not move" bugs are mobile `@media` overrides of the same selector; comments or linting around desktop/mobile paired rules would help.
- Dead code pass for old routes, stale feature flags, and unused UI states.

## Frontend

- Expand the Editor for quicker, more robust everyday use. Better file/document
  handling, smoother window behavior, clearer save/export flows, stronger image
  editing affordances, and fewer brittle edge cases.
- Better AI integration for Notes and Todos. Notes should be easier for the
  agent to read, update, summarize, and turn into actions. Todos should be
  assignable to an agent from the UI, possibly through a button, task action,
  or dedicated skill/tool flow.
- Mobile gallery/editor polish. Easier to launch/download inpaint model or any missing pieces.
- Accessibility pass: keyboard navigation, focus states, contrast, reduced motion.
- Improve empty states and error messages on fresh installs.
- Tighten first-run setup, hints, and tours so they do not repeat or fight each other.
- Vendor CDN assets eventually for a more fully self-hosted/offline mode.

## Backend

- More tests around endpoint probing and provider setup.
- Better task scheduler defaults and visibility.
- Backup/restore guide and helper flow for `data/`.
- Security hardening around admin-only tools and clear docs for their risk.

## Not The Focus Right Now

I prob shouldnt add more themes.
