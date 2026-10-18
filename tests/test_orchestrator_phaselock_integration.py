"""Integration: CanonicalLoop + real ToolRegistry gates tools per phase."""

from src.orchestrator.loop import CanonicalLoop
from src.orchestrator.phases import Phase
from src.tool_registry import ToolRegistry


def _registry():
    # Fresh registry bound to the real project config (not the singleton, to
    # avoid cross-test contamination of session phases).
    return ToolRegistry(config_path="config/phase-lock.yaml")


def test_classify_blocks_writes_build_allows_them():
    reg = _registry()
    loop = CanonicalLoop(session_id="itest", registry=reg)

    # CLASSIFY: write_file must be blocked.
    loop.goto(Phase.CLASSIFY)
    res = reg.is_tool_allowed("write_file", "itest")
    assert res["allowed"] is False
    assert res["phase"] == "CLASSIFY"

    # BUILD: write_file must be allowed.
    loop.goto(Phase.BUILD)
    res = reg.is_tool_allowed("write_file", "itest")
    assert res["allowed"] is True
    assert res["phase"] == "BUILD"


def test_quality_allows_pytest_blocks_arbitrary_bash():
    reg = _registry()
    loop = CanonicalLoop(session_id="itest2", registry=reg)
    loop.goto(Phase.QUALITY)

    ok = reg.is_tool_allowed("bash", "itest2", {"command": "pytest tests/"})
    assert ok["allowed"] is True

    blocked = reg.is_tool_allowed("bash", "itest2", {"command": "rm -rf build"})
    assert blocked["allowed"] is False


def test_full_walk_sets_phase_each_step():
    reg = _registry()
    loop = CanonicalLoop(session_id="itest3", registry=reg)
    loop.apply()
    phases_seen = [reg.get_phase("itest3")]
    while loop.advance():
        loop.apply()
        phases_seen.append(reg.get_phase("itest3"))
    assert phases_seen == [
        "CLASSIFY",
        "KNOW",
        "PLAN",
        "BUILD",
        "QUALITY",
        "AUTOEVAL",
        "MEMORY_OBSERVE",
    ]
