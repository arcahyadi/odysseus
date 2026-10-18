"""Tests for src/orchestrator/spec.py — parsing .opencode agent Markdown."""

import textwrap

from src.orchestrator.spec import AgentSpec, parse_agent_spec


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def test_parses_frontmatter_name_and_description(tmp_path):
    p = _write(
        tmp_path,
        "gsd-planner.md",
        """\
        ---
        name: gsd-planner
        description: Creates phase plans from goals.
        ---
        # Role

        The planner does X.
        """,
    )
    spec = parse_agent_spec(p)
    assert isinstance(spec, AgentSpec)
    assert spec.name == "gsd-planner"
    assert spec.description == "Creates phase plans from goals."
    assert "The planner does X." in spec.prompt
    assert spec.prompt.startswith("# Role")
    assert spec.tools == []
    assert spec.model is None
    assert spec.source_path == str(p)


def test_parses_tools_list(tmp_path):
    p = _write(
        tmp_path,
        "security-audit.md",
        """\
        ---
        name: security-audit
        description: STRIDE audit.
        tools:
          - read_file
          - grep
        ---
        # Role
        Audit stuff.
        """,
    )
    spec = parse_agent_spec(p)
    assert spec.tools == ["read_file", "grep"]


def test_multiline_folded_description(tmp_path):
    p = _write(
        tmp_path,
        "constitution.md",
        """\
        ---
        name: constitution
        description: >
          Constitution agent — encodes the invariants.
          Run before any agentic workflow.
        ---
        # Body
        """,
    )
    spec = parse_agent_spec(p)
    assert spec.description.startswith("Constitution agent")
    assert "Run before any agentic workflow." in spec.description


def test_no_frontmatter_derives_name_from_filename(tmp_path):
    p = _write(
        tmp_path,
        "open-design.md",
        """\
        # Open Design Agent

        Génère des artefacts de design depuis un brief.
        """,
    )
    spec = parse_agent_spec(p)
    assert spec.name == "open-design"
    assert spec.description == ""
    assert spec.prompt.startswith("# Open Design Agent")
    assert spec.tools == []


def test_explicit_model_key_is_read(tmp_path):
    p = _write(
        tmp_path,
        "x.md",
        """\
        ---
        name: x
        description: d
        model: openai/kimi-k2.7-code
        ---
        body
        """,
    )
    spec = parse_agent_spec(p)
    assert spec.model == "openai/kimi-k2.7-code"


def test_agentspec_is_frozen(tmp_path):
    p = _write(tmp_path, "x.md", "---\nname: x\ndescription: d\n---\nbody\n")
    spec = parse_agent_spec(p)
    try:
        spec.name = "mutated"
        raised = False
    except Exception:
        raised = True
    assert raised, "AgentSpec must be immutable (frozen dataclass)"
