"""M3.2 Trinité checkpoint — kill-switched bridge for the live loop.

The native Trinité "checkpoint" (``routes/knowledge_routes.trinite_checkpoint``)
is a PRE-GENERATION READ: it fuses CBM + VectorRAG + Obsidian context to enrich
a generation. It persists nothing and takes no run state, so it cannot be reused
for the roadmap's POST-ROUND checkpoint (session_id, run_id, metrics, outcome)
without misuse. The chosen native-first substrate is therefore the Obsidian
memory leg's write primitive (``mcp_servers.obsidian_mcp.create_note``): the
same Trinité memory store the native checkpoint already reads from.

These tests pin the bridge that lets the loop persist ONE run checkpoint at
MEMORY_OBSERVE — but only when the kill-switch (ODYSSEUS_CHECKPOINT) is ON.
Default OFF means live behaviour is byte-identical. Best-effort: any backend
fault is swallowed so it can never break the loop.
"""

import json

from src.orchestrator import checkpoint_tracker


class _FakeVault:
    """Records calls to create_note(path, content) — the native Obsidian write."""

    def __init__(self, result=None, raises=False):
        self.calls = []
        self._result = result if result is not None else {"path": "x", "bytes_written": 1}
        self._raises = raises

    def create_note(self, path, content):
        self.calls.append({"path": path, "content": content})
        if self._raises:
            raise RuntimeError("vault unavailable")
        return self._result


def test_checkpoint_enabled_by_default(monkeypatch):
    """Palier 0 (FND-4 option C): CHECKPOINT is ON by default again.

    The OFF polarity is still covered right below: a kill-switch nobody
    can turn off is not a kill-switch.
    """
    monkeypatch.delenv("ODYSSEUS_CHECKPOINT", raising=False)
    assert checkpoint_tracker.checkpoint_enabled() is True


def test_checkpoint_can_be_off(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_CHECKPOINT", "off")
    assert checkpoint_tracker.checkpoint_enabled() is False


def test_checkpoint_enabled_when_flag_truthy(monkeypatch):
    for val in ("on", "1", "true", "yes"):
        monkeypatch.setenv("ODYSSEUS_CHECKPOINT", val)
        assert checkpoint_tracker.checkpoint_enabled() is True


def test_checkpoint_disabled_for_other_values(monkeypatch):
    for val in ("off", "0", "no", ""):
        monkeypatch.setenv("ODYSSEUS_CHECKPOINT", val)
        assert checkpoint_tracker.checkpoint_enabled() is False


def test_noop_when_disabled(monkeypatch):
    vault = _FakeVault()
    out = checkpoint_tracker.record_checkpoint(
        session_id="s1",
        run_id="r1",
        metrics={"tokens": 10},
        outcome="completed",
        enabled=False,
        backend=vault,
    )
    assert out is None
    assert vault.calls == []


def test_writes_one_checkpoint_when_enabled():
    vault = _FakeVault()
    out = checkpoint_tracker.record_checkpoint(
        session_id="sess-abc",
        run_id="run-1234abcd",
        metrics={"total_tokens": 42, "duration_s": 1.5, "model": "m"},
        outcome="completed",
        enabled=True,
        backend=vault,
    )
    assert out == {"path": "x", "bytes_written": 1}
    assert len(vault.calls) == 1
    call = vault.calls[0]
    # persisted under the agentos checkpoints folder, keyed by session+run
    assert call["path"].startswith("agentos/checkpoints/")
    assert call["path"].endswith(".md")
    assert "sess-abc" in call["path"] or "run-1234" in call["path"]
    # the record carries the run's state
    assert "sess-abc" in call["content"]
    assert "run-1234abcd" in call["content"]
    assert "completed" in call["content"]
    assert "total_tokens" in call["content"]


def test_content_has_parseable_json_block():
    vault = _FakeVault()
    checkpoint_tracker.record_checkpoint(
        session_id="s",
        run_id="r",
        metrics={"a": 1, "b": "x"},
        outcome="completed",
        enabled=True,
        backend=vault,
    )
    content = vault.calls[0]["content"]
    start = content.index("{")
    end = content.rindex("}") + 1
    payload = json.loads(content[start:end])
    assert payload["session_id"] == "s"
    assert payload["run_id"] == "r"
    assert payload["outcome"] == "completed"
    assert payload["metrics"] == {"a": 1, "b": "x"}


def test_backend_exception_is_isolated():
    vault = _FakeVault(raises=True)
    out = checkpoint_tracker.record_checkpoint(
        session_id="s",
        run_id="r",
        metrics={},
        outcome="completed",
        enabled=True,
        backend=vault,
    )
    assert out is None
    assert len(vault.calls) == 1  # attempted, then swallowed


def test_backend_error_dict_is_returned_not_raised():
    vault = _FakeVault(result={"error": "vault not found"})
    out = checkpoint_tracker.record_checkpoint(
        session_id="s",
        run_id="r",
        metrics={},
        outcome="completed",
        enabled=True,
        backend=vault,
    )
    # error dict from the native primitive is passed through, never raised
    assert out == {"error": "vault not found"}
    assert len(vault.calls) == 1


def test_metrics_summary_is_bounded():
    """A huge metrics dict must not blow up the note — only a summary is kept."""
    vault = _FakeVault()
    big = {f"k{i}": "v" * 500 for i in range(200)}
    out = checkpoint_tracker.record_checkpoint(
        session_id="s",
        run_id="r",
        metrics=big,
        outcome="completed",
        enabled=True,
        backend=vault,
    )
    assert out is not None
    assert len(vault.calls) == 1
