"""
Regression guards for the tour-core.js extraction.

Task #14 hoisted the tour primitives (ensureTourStyles / clearComposer /
makeHalo / positionTooltip / beginSession / runTour / cancelActiveTour) out
of slashCommands.js so the linear tours stop re-declaring them. These tests
are source-level: they check the JS text, not the runtime behavior, because
running real tours requires a browser and we're guarding against *drift*
(e.g. someone copy-pasting the CSS back into a handler).

If a future change legitimately moves these, update the assertions rather
than deleting them.
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOUR_CORE = REPO / "static" / "js" / "tour-core.js"
SLASH = REPO / "static" / "js" / "slashCommands.js"
SW = REPO / "static" / "sw.js"
AUTOPLAY = REPO / "static" / "js" / "tourAutoplay.js"


@pytest.fixture(scope="module")
def core_src():
    return TOUR_CORE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def slash_src():
    return SLASH.read_text(encoding="utf-8")


def test_tour_core_exists_and_exports_primitives(core_src):
    # Every helper the multi-phase tours reach for must be exported by name.
    for name in (
        "ensureTourStyles",
        "clearComposer",
        "makeHalo",
        "pollForModal",
        "positionTooltip",
        "beginSession",
        "runTour",
        "cancelActiveTour",
        "sleep",
    ):
        present = (
            f"export function {name}" in core_src
            or f"export async function {name}" in core_src
        )
        assert present, f"tour-core.js missing export {name}"


def test_tour_core_installs_global_cancel(core_src):
    # tourAutoplay.js and modal-close handlers call `window.cancelActiveTour`.
    # tour-core must own that wiring now that slashCommands.js dropped its
    # local closure.
    assert "window.cancelActiveTour = cancelActiveTour" in core_src


def test_tour_css_string_appears_exactly_once_in_core(core_src, slash_src):
    # tour-core owns the canonical copy of the tooltip CSS.
    assert core_src.count("position:fixed;z-index:10001;background:var(--bg)") == 1
    # slashCommands.js used to carry 6 copies (one per tour handler). After
    # the extraction, only _runChatTour's template-literal variant remains
    # — it extends the base rules with .tour-arrow / .tour-btn-arrow-pulse
    # — and even that shares the same first-line selector text.
    # The concat form (which is what the 5 tour handlers used) is gone.
    assert "s.textContent =\n      '#tour-tooltip{position:fixed" not in slash_src
    assert "ensureTourStyles();" in slash_src


@pytest.mark.parametrize("handler", [
    "_cmdTourTheme", "_cmdTourSettings", "_cmdTourGallery",
    "_cmdTourNotes", "_cmdTourBrain",
])
def test_linear_tours_have_no_inlined_tour_css(slash_src, handler):
    """The 5 migrated handlers must not redeclare the tour-tooltip CSS.

    Multi-phase handlers (Compare/Cookbook/Research/Library/Tasks) still
    inject their own copy of the block — they were intentionally left alone
    this pass because their phase-boundary waits depend on precise DOM
    sequencing. This test keeps the migrated handlers honest.
    """
    start = slash_src.index(f"async function {handler}(")
    rest = slash_src[start:]
    end_rel = len(rest)
    for marker in ("\nasync function ", "\n// ── "):
        idx = rest.find(marker, len(f"async function {handler}("))
        if idx != -1 and idx < end_rel:
            end_rel = idx
    body = rest[:end_rel]
    assert "position:fixed;z-index:10001;background:var(--bg)" not in body


def test_slash_commands_imports_tour_core(slash_src):
    assert "from './tour-core.js'" in slash_src, "slashCommands.js must import tour-core"
    # runTour is what the 5 linear handlers call; ensureTourStyles/makeHalo/
    # clearComposer are what the multi-phase handlers may reuse.
    assert "runTour" in slash_src
    assert "ensureTourStyles" in slash_src


def test_slash_commands_dropped_local_cancel(slash_src):
    # The old hand-rolled `window.cancelActiveTour = function cancelActiveTour()
    # { ... }` block at the top of the file is gone; tour-core installs it.
    assert "window.cancelActiveTour = function" not in slash_src


@pytest.mark.parametrize(
    "handler",
    [
        "_cmdTourTheme",
        "_cmdTourSettings",
        "_cmdTourGallery",
        "_cmdTourNotes",
        "_cmdTourBrain",
    ],
)
def test_linear_tours_delegate_to_run_tour(slash_src, handler):
    """The 5 linear handlers should be a single runTour(...) call, not a
    hand-rolled _showStep/_makeHalo/_positionTooltip closure stack."""
    start = slash_src.index(f"async function {handler}(")
    # Find the next top-level `async function` or `// ── ` marker.
    rest = slash_src[start + len(f"async function {handler}("):]
    end_rel = len(rest)
    for marker in ("\nasync function ", "\n// ── "):
        idx = rest.find(marker)
        if idx != -1 and idx < end_rel:
            end_rel = idx
    body = slash_src[start:start + len(f"async function {handler}(") + end_rel]

    assert "runTour({" in body, f"{handler} should delegate to runTour"
    # The whole point of the refactor: no duplicated closure machinery inside
    # linear handlers.
    assert "function _makeHalo" not in body, f"{handler} still has local _makeHalo"
    assert "function _positionTooltip" not in body, f"{handler} still has local _positionTooltip"
    assert "function _showStep" not in body, f"{handler} still has local _showStep"


def test_halo_track_appear_option_supported(core_src):
    """Settings/Gallery/Notes/Brain tracked the modal-enter animation with a
    500ms rafId re-measure loop; tour-core must expose that as an option so
    they don't need their own _makeHalo anymore."""
    assert "trackAppear" in core_src
    assert "haloTracksAppear" in core_src


def test_run_tour_supports_on_finish(core_src):
    """Settings and Gallery land on a friendly starting tab after the last
    step, before clearing — that behavior is now the `onFinish` hook."""
    assert "onFinish" in core_src


def test_precache_includes_tour_core():
    sw = SW.read_text(encoding="utf-8")
    # slashCommands.js imports tour-core.js at module load, so a first-boot
    # offline install that only precached slashCommands would fail the
    # ES-module resolution chain.
    assert "/static/js/tour-core.js" in sw


def test_cache_name_bumped_for_tour_core():
    import re
    sw = SW.read_text(encoding="utf-8")
    # tour-core.js landed alongside a bump to v348 (last was v347). Any later
    # precached module must keep the cache version at or above that, or existing
    # installs serve a stale shell. Guard the minimum rather than an exact pin so
    # a legitimate future bump (e.g. adding multiModel/index.js) doesn't break it.
    m = re.search(r"CACHE_NAME\s*=\s*'odysseus-v(\d+)'", sw)
    assert m, "sw.js must define CACHE_NAME = 'odysseus-v<NNN>'"
    assert int(m.group(1)) >= 348, (
        f"cache version {m.group(1)} is below the tour-core bump (348); "
        "adding a precached module requires bumping CACHE_NAME"
    )


def test_autoplay_map_covers_all_linear_tour_modals():
    autoplay = AUTOPLAY.read_text(encoding="utf-8")
    # Every modal opened by a linear tour should have an autoplay entry so a
    # future re-enable of the (currently disabled) autoplay init() picks them
    # up without extra work.
    for modal in (
        "theme-modal",
        "settings-modal",
        "gallery-modal",
        "memory-modal",       # Brain tour
        "notes-pane",         # Notes tour (side sheet)
    ):
        assert f"'{modal}'" in autoplay, f"TOUR_FOR_MODAL missing {modal}"
