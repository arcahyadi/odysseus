"""Tests for src/orchestrator/registry.py — discovery of agent specs."""

import textwrap

from src.orchestrator.registry import AgentRegistry


def _agent(dir_path, filename, name):
    (dir_path / filename).write_text(
        textwrap.dedent(f"""\
            ---
            name: {name}
            description: desc for {name}
            ---
            # Role
            Body of {name}.
            """),
        encoding="utf-8",
    )


def test_discovers_all_agents(tmp_path):
    _agent(tmp_path, "a.md", "alpha")
    _agent(tmp_path, "b.md", "beta")
    reg = AgentRegistry(tmp_path)
    reg.discover()
    assert set(reg.list_names()) == {"alpha", "beta"}


def test_get_returns_spec(tmp_path):
    _agent(tmp_path, "a.md", "alpha")
    reg = AgentRegistry(tmp_path)
    reg.discover()
    spec = reg.get("alpha")
    assert spec is not None
    assert spec.name == "alpha"
    assert "Body of alpha." in spec.prompt


def test_get_unknown_returns_none(tmp_path):
    reg = AgentRegistry(tmp_path)
    reg.discover()
    assert reg.get("nope") is None


def test_missing_directory_yields_empty_registry(tmp_path):
    reg = AgentRegistry(tmp_path / "does-not-exist")
    reg.discover()
    assert reg.list_names() == []


def test_broken_file_is_skipped_not_fatal(tmp_path):
    _agent(tmp_path, "good.md", "good")
    # A file that cannot be read as expected must not crash discovery.
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe not utf-8 \xff")
    reg = AgentRegistry(tmp_path)
    reg.discover()
    assert "good" in reg.list_names()


def test_discover_is_idempotent(tmp_path):
    _agent(tmp_path, "a.md", "alpha")
    reg = AgentRegistry(tmp_path)
    reg.discover()
    reg.discover()
    assert reg.list_names().count("alpha") == 1
