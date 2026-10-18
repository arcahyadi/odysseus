"""Tests for src/orchestrator/gate.py — catastrophic command gate."""

from src.orchestrator.gate import gate_enabled, should_block_destructive


def test_blocks_rm_rf():
    reason = should_block_destructive("bash", {"content": "rm -rf /"})
    assert reason is not None
    assert "bloqu" in reason.lower() or "block" in reason.lower()


def test_blocks_fork_bomb():
    assert should_block_destructive("bash", {"content": ":(){:|:&};:"}) is not None


def test_blocks_drop_database():
    assert should_block_destructive("python", {"content": "cur.execute('drop database prod')"}) is not None


def test_blocks_dd_and_mkfs():
    assert should_block_destructive("bash", {"content": "dd if=/dev/zero of=/dev/sda"}) is not None
    assert should_block_destructive("bash", {"command": "mkfs.ext4 /dev/sdb"}) is not None


def test_allows_normal_bash():
    assert should_block_destructive("bash", {"content": "ls -la && pytest"}) is None


def test_does_not_block_explicit_delete_tool():
    # delete_file is DESTRUCTIVE in the tool map, but it is an explicit user tool
    # with its own semantics — the catastrophic-command gate must NOT block it.
    assert should_block_destructive("delete_file", {"path": "notes/tmp.md"}) is None
    assert should_block_destructive("stop_served_model", {"id": "x"}) is None


def test_reads_command_key_too():
    assert should_block_destructive("bash", {"command": "rm -rf /var"}) is not None


def test_gate_can_be_disabled_by_env(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_DESTRUCTIVE_GATE", "off")
    assert gate_enabled() is False
    # When disabled, should_block_destructive still classifies but callers skip it;
    # the function itself is pure and unaffected — enforcement is gated by gate_enabled().
    assert should_block_destructive("bash", {"content": "rm -rf /"}) is not None


def test_gate_enabled_default_true(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_DESTRUCTIVE_GATE", raising=False)
    assert gate_enabled() is True


def test_gate_enabled_explicit_on(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_DESTRUCTIVE_GATE", "on")
    assert gate_enabled() is True
