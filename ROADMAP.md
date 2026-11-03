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

## Completed

Landed since the last pass (verified against the code and `tests/` on 2026-10-02):

- **Better degraded-state reporting for ChromaDB, SearXNG, email, ntfy, and
  provider probes.** `src/service_health.py` consolidates every subsystem into
  one uniform, non-intrusive probe (`ok|degraded|down|disabled`), backed by an
  admin-only endpoint with bounded wall-clock fan-out and no secret leakage.
- **Skill/tool prompt-injection audit.** User-editable surfaces
  (`email_writing_style`, integration descriptions, MCP tool descriptions) are
  now wrapped in `untrusted_context_message()` (`trusted=False`) instead of being
  concatenated into the trusted system role. Regression: `tests/test_prompt_injection_audit.py`,
  `tests/test_skill_index_prompt_injection.py`, `tests/test_tool_output_prompt_injection.py`.
- **Cookbook failure diagnosis / error feedback.** `_diagnose_serve_output`
  turns serve/download failures (CUDA OOM, port-in-use, missing deps) into a
  message + actionable next-step suggestions, with error tail lines surfaced to
  the UI instead of a bare "crashed". Tests: `test_cookbook_error_feedback.py`,
  `test_cookbook_error_tail_lines.py`, `test_cookbook_diagnosis*`.
- **Backup/restore guide and helper flow for `data/`.** `scripts/odysseus-backup`
  snapshot/restore CLI (SQLite via its `.backup` API, safe while running),
  `routes/backup_routes.py`, and `docs/backup-restore.md`.
- **More tests around endpoint probing and provider setup.**
  `test_endpoint_probing.py` plus the provider detection/classification/endpoints
  suites and the `service_health` provider probe.
- **CDN assets vendored locally.** KaTeX 0.16.22 (css + js + 60 font files)
  now lives under `static/lib/katex/`, Mermaid 11 under
  `static/lib/mermaid/mermaid.min.js`, and the two `docs/index.html`
  testimonial avatars under `docs/assets/`. `scripts/vendor_cdn_assets.py`
  is the reproducible fetcher if the pinned versions ever need bumping.
  `core/middleware.py`'s CSP drops jsdelivr from `style-src` and
  `font-src`; `script-src` still allows it solely for Pyodide, which is
  loaded lazily by `codeRunner.js` and whose wheel bundle (~200 MB) is
  impractical to ship in the repo.
- **Windows test harness fixed.** Drove the native-Windows pytest run from
  ~123 failures to a green **4678 passed / 14 skipped** suite on 2026-10-03.
  Three portable-testing methodologies came out of the pass and are the pattern
  to follow for future Windows-only tests:
  - *Encoding*: pin `encoding="utf-8"` (and `errors="replace"` where needed) on
    every `subprocess.run(text=True)` and `Path.read_text()` that touches
    UTF-8 source or output. The Windows default locale is `cp1252`, so
    `→`, `·`, and similar chars in our JS/static files crashed Node stdin and
    regex readers. Also switch `Path(...).as_posix()` → `.as_uri()` when the
    path is fed to Node's `--input-type=module` (ESM requires `file://`).
  - *Platform guards*: `@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), …)`
    for unix-socket tests, `@pytest.mark.skipif(sys.platform == "win32", …)`
    for `IS_APPLE_SILICON` (which gates on `IS_POSIX`) and `os.X_OK` exec-bit
    semantics, and `core.platform_compat.find_bash()` + skipif when running
    `.sh` scripts (PATH-resolved `bash` on Windows is often a WSL shim that
    fails `execvpe(/bin/bash)`).
  - *Windows-branch bypass via monkeypatch*: force `IS_WINDOWS=False` or stub
    `_detect_windows` to return `None` so POSIX-only code paths (tmux probe,
    generic hardware detection) can be exercised deterministically on any
    host. Same pattern for env-var isolation: `_npm_cache_roots()` scans
    `%LOCALAPPDATA%\npm-cache` and `expanduser("~")` prefers `USERPROFILE`
    over `HOME` on Windows, so tests must redirect HOME + USERPROFILE +
    LOCALAPPDATA together.
  Two product-side Windows-portability fixes landed alongside:
  `_tool_path_roots()` in `src/tool_execution.py` now includes the OS-native
  temp root via `tempfile.gettempdir()` plus `%TEMP%`/`%TMP%` (previously
  only `/tmp`, TMPDIR — tools were denied write access to their scratch dir
  on Windows); `_is_sensitive_path()` splits on both `/` and `\` so forward-
  slash paths arriving through JSON / model output cannot fail-open past the
  deny-list. Two declared-but-uninstalled deps (`nh3`, `icalendar`) were
  added back to the environment — the 12 collection errors they caused are
  gone.

Partially addressed — **Agent prompt/context bloat**: the adaptive input-token
budget (`src/context_budget.py`, #1170) and history compaction
(`src/context_compactor.py`) now scale the prompt to the model's discovered
context window, and the tool RAG retrieval width plus the always-available
baseline tier down for tight windows via
`src/context_budget.compute_tool_retrieval_k` /
`src/tool_index.ALWAYS_AVAILABLE_SMALL`. Skills/documents/instructions
still ride along; further slimming remains open.

## High Priority

- SQUASH BUGS
- Fresh install smoke tests on Linux, macOS, and Windows. Docker, native Python,
  and WSL all need coverage. _(Native Python done: `tests/smoke/test_first_boot.py`
  runs against a pristine `ODYSSEUS_DATA_DIR` in a subprocess and CI's
  `first-boot-smoke` matrix exercises it on ubuntu-latest / windows-latest /
  macos-14. Docker + WSL matrices still open.)_

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
  _(Done: `GET /api/cookbook/hf-latest` now converts each trending entry into
  an hwfit record and ranks it via `services.hwfit.fit.analyze_model`, which
  already handles architecture bonus, quant quality penalty, VRAM/RAM fit and
  backend support. Trending downloads are only a small tiebreaker bump.)_
- Agent prompt/context bloat. Agent mode is too heavy for smaller local models:
  tool schemas, skills, memory, documents, and instructions can eat the context
  before the user request really starts. We need slimmer prompts, better tool
  selection, smaller default tool sets, and clearer guidance for models with
  4k/8k/16k context windows.
  _(Tool-side tiering landed: `compute_tool_retrieval_k` narrows RAG width to
  4/5/8/12 for sub-4K / sub-8K / sub-32K / ≥32K windows, and
  `ALWAYS_AVAILABLE_SMALL` (ask_user + update_plan) is the baseline when the
  window is under 8K. Skills/documents/instructions still ride along; further
  prompt slimming remains open.)_
- Email performance audit. Fetching, searching, opening, deleting, and sending
  email can feel slow, especially over IMAP/SMTP providers with high latency.
  Need someone who knows mail performance to profile the current flow, identify
  whether the bottleneck is IMAP folder select/fetch, cache invalidation,
  attachment/body loading, SMTP handshakes, or frontend refresh behavior, then
  propose safer caching/prefetch/batching without breaking multi-account state.
- Provider setup/probing audit for Anthropic, Gemini, Groq, xAI, OpenRouter, OpenAI, and DeepSeek.

## Media Suite (Photoshop → Video) — subsections of Odysseus, not a standalone project

> **"Write text. Receive a documentary."** — an image/video capability area
> that lives *inside* Odysseus. Every piece below is a feature of the app and
> is built by **reusing Odysseus's existing substrate** (agent tools +
> `tool_index`, `PlanExecutor`, `bg_jobs`, Cookbook service discovery, hwfit,
> `tts_routes`, the Gallery asset store). It is deliberately **not** a separate
> CLI, repo, or `main.py`. Zero-cost local-first policy throughout: no paid
> APIs, subscriptions, prepaid credits, or rented GPUs are valid production
> dependencies. Cloud is off by default; if no practical zero-cost backend is
> available the pipeline *waits* rather than calling a paid service.

**Shared foundation to build on (all already in the app):**
- **Orchestration** — `services/planning/executor.py` `PlanExecutor` (episode =
  a plan, shot = a step; resumable, per-step status/error, live progress UI in
  `plan-tracker.js` / `plans-panel.js`) + `src/bg_jobs.py` for multi-minute
  render legs (`#!bg` auto-reinvoke, never blocks chat).
- **Image backends** — Cookbook discovers/serves ComfyUI / A1111 / Forge
  (`src/tools/cookbook.py`); `scripts/diffusion_server.py` serves SDXL / SD3.5
  / Flux via an OpenAI-compatible `/v1/images/generations`; `services/hwfit`
  picks the model that fits the box's VRAM/RAM.
- **Voiceover** — `routes/tts_routes.py`. **Output/media** — the Gallery store.
- **Entry surface** — a `/documentary <topic|outline>` slash command + agent
  tools registered in `tool_index`/`tool_schemas`, so it composes with memory,
  documents, and Deep Research and respects context-window tiering.
- **Providers** stay thin adapters over the routing above (ImageProvider→
  endpoint, TTSProvider→tts_routes, LLM→agent model routing) with `Mock*`
  variants for a no-GPU dry run. No parallel provider stack.

### 1. Photoshop (image editor) — mostly DONE
The gallery editor (`static/js/editor/` + `static/js/galleryEditor.js`, backend
`src/tools/image.py::do_edit_image`) is already a layered, Photoshop-class
editor: layer + mask system, brush, clone, transform, crop, filters, curves,
histogram, and AI inpaint / rembg / harmonize (`ai-inpaint.js`, `ai-rembg.js`,
`harmonize-masks.js`).
Remaining pro gap (polish, not a rebuild):
- Fuller type/text tool (only a stub today — 1 reference), paragraph/leading
  controls, and text-on-a-layer as editable vector.
- Adjustment layers + non-destructive curves/levels/colour-balance (curve code
  is minimal today), smart-object-style re-editable transforms.
- Selection refine (feather/contract/select-inverse parity) and channel/mask
  workflows surfaced in the UI.

### 2. Documentary compiler (formerly "Understanding Studio") — NEW, not started
Turns a high-level outline — or just a **topic**, which Odysseus can research
into an outline via Deep Research/web/memory — into a narrated MP4 episode.
As an episode `Plan` executed by `PlanExecutor`:

- **Screenplay / shot expansion** — LLM expands the outline into an ordered
  shot list (target ≈60 shots / ~8 min) validated by strict Pydantic schemas so
  fields cannot hallucinate; exponential backoff on local-provider rate limits.
- **Continuity (the hard part)** — a first-class per-episode **"bible"**
  (characters, style tokens, palette, locked seeds) persisted in the doc store
  and injected into every shot prompt; + IP-Adapter / reference-image when
  ComfyUI is present. This is what makes dozens of sequential shots feel
  authored rather than random.
- **Stills** — generate per shot through the local image backend chosen by
  hwfit (diffusion_server today; ComfyUI when a live graph is available).
- **Motion + assembly** — deterministic camera moves (pan / zoom / dolly /
  fade / Ken-Burns) applied to stills via **FFmpeg**, then auto-assemble
  voiceover + motion clips into a timeline / concatenated MP4 landed in Gallery.

**Rendering modes (both run inside Odysseus, no separate CLI):**
- *Production*: local diffusion_server / ComfyUI → FFmpeg motion. Cloud off by
  default; a HuggingFace free tier only behind an explicit
  `UNDERSTANDING_ENABLE_FREE_CLOUD=1` after confirming no payment path. Paid
  providers (Runway, Stability) are never selected.
- *Dry run*: `MockImageProvider` + `MockTTSProvider` (placeholder frames +
  silent audio) validate screenplay → shot-plan → FFmpeg assembly end-to-end
  with **no GPU / no API calls** — the first milestone to build, since it
  proves the pipeline shape against the existing executor.

**Deferred / gated:**
- **Real text-to-video** (LTX-Video / SVD / Wan) stays isolated from production.
  The **OpenVINO LTX-Video gate** proves a single local, zero-cost clip on an
  Intel GPU first (INT8; dims divisible by 32, frames divisible by 8 + 1; own
  venv; emits `real_video.avi` + `report.json`; **passes only when a real clip
  exists**, with perf + peak RSS captured for the continue/stop call). Whether
  a box even attempts it is decided by **hwfit**, not a hand-run script.
- **Audio polish** — background music with automatic ducking under narration,
  plus generated SRT subtitle tracks.
- **Screenplay enhancement** — tune prompts for more compelling, emotionally
  resonant documentary pacing.

### 3. Video editor / NLE ("Premiere-style") — NEW, not started
An editor for manual assembly and polish on top of (or independent of) compiled
episodes. **Better path than a browser GPU-compositor:** the compiler emits an
**editable timeline as data (JSON / EDL)**; the NLE is a thin timeline UI that
delegates all pixel/audio work back to server-side FFmpeg via `bg_jobs`, so it
stays re-editable without shipping a rendering engine in JS.
- Multi-track timeline (video + audio), clip trim / split / ripple, transitions.
- Keyframeable transforms + the same camera-motion vocabulary the compiler uses
  (pan/zoom/fade), so compiled episodes are re-editable, not final-only.
- Audio tracks reusing the ducking/mixer from the compiler's audio-polish item.
- Export presets (res / codec / container) run through `#!bg` background jobs so
  long renders never block the chat.

## Refactor Targets
- CSS cleanup. `static/style.css` basically Calypso's island atm.
- Tour core helper. The onboarding tours have too much copy-pasted scaffolding; promote a shared `tour-core.js` helper before adding more tours.
  _(Partially done: `static/js/tour-core.js` now owns `ensureTourStyles` /
  `clearComposer` / `makeHalo` / `pollForModal` / `positionTooltip` /
  `beginSession` / `runTour` / `cancelActiveTour`. The 5 linear tours
  (Theme/Settings/Gallery/Notes/Brain) call `runTour({...})` in a single
  shot; the 5 multi-phase handlers (Compare/Cookbook/Library/Research/Tasks)
  and `_runChatTour` still drive halos/tooltip directly, but they all use
  `ensureTourStyles()` for the CSS block. Guards live in
  `tests/test_tour_core_extraction.py`. Remaining: migrate multi-phase
  handlers to `beginSession(...)` so the halo/step closures come from one
  place too.)_
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

## Backend

- Better task scheduler defaults and visibility.
- Security hardening around admin-only tools and clear docs for their risk.

## Not The Focus Right Now

I prob shouldnt add more themes.
