# tool_access.rego — Phase-aware tool authorization for Odysseus agents.
# Maps each canonical phase to allowed tool categories.
# Hot-reloadable via OPA bundle or direct file mount.

package odysseus.tool

default allow = false

# ── BUILD: full access ────────────────────────────────────────
allow {
    input.phase == "BUILD"
}

# ── PLAN: read + search + knowledge + draft only ─────────────
allow {
    input.phase == "PLAN"
    input.tool_category in {"READ", "SEARCH", "KNOWLEDGE", "DRAFT"}
}

# ── PLAN write_restriction: only allowed paths ───────────────
allow {
    input.phase == "PLAN"
    input.tool_category == "WRITE"
    input.write_path != ""
    startswith(input.write_path, "process/")
}

allow {
    input.phase == "PLAN"
    input.tool_category == "WRITE"
    input.write_path != ""
    startswith(input.write_path, ".planning/")
}

allow {
    input.phase == "PLAN"
    input.tool_category == "WRITE"
    input.write_path != ""
    startswith(input.write_path, ".opencode/")
}

# ── CLASSIFY: read-only ──────────────────────────────────────
allow {
    input.phase == "CLASSIFY"
    input.tool_category in {"READ", "SEARCH", "KNOWLEDGE"}
}

# ── KNOW: read + search + knowledge ──────────────────────────
allow {
    input.phase == "KNOW"
    input.tool_category in {"READ", "SEARCH", "KNOWLEDGE"}
}

# ── RESEARCH: read + search + knowledge ─────────────────────
allow {
    input.phase == "RESEARCH"
    input.tool_category in {"READ", "SEARCH", "KNOWLEDGE"}
}

# ── INNOVATE: read + search + knowledge + draft ──────────────
allow {
    input.phase == "INNOVATE"
    input.tool_category in {"READ", "SEARCH", "KNOWLEDGE", "DRAFT"}
}

# ── VERIFY: read + search + knowledge + test exec only ───────
allow {
    input.phase == "VERIFY"
    input.tool_category in {"READ", "SEARCH", "KNOWLEDGE"}
}

# VERIFY exec_restriction: only test commands
allow {
    input.phase == "VERIFY"
    input.tool_category == "EXEC"
    input.tool_name in {"bash", "python"}
    _is_test_command(input.command)
}

# ── QUALITY: read + search + knowledge + test/lint exec ──────
allow {
    input.phase == "QUALITY"
    input.tool_category in {"READ", "SEARCH", "KNOWLEDGE"}
}

allow {
    input.phase == "QUALITY"
    input.tool_category == "EXEC"
    input.tool_name in {"bash", "python"}
    _is_test_or_lint_command(input.command)
}

# ── AUTOEVAL: read + search + knowledge + exec (no destructive) ─
allow {
    input.phase == "AUTOEVAL"
    input.tool_category in {"READ", "SEARCH", "KNOWLEDGE", "EXEC"}
}

# ── MEMORY_OBSERVE: read + search + knowledge + write (no destructive) ──
allow {
    input.phase == "MEMORY_OBSERVE"
    input.tool_category in {"READ", "SEARCH", "KNOWLEDGE", "WRITE"}
}

# ── Destructive tools: always require explicit approval ──────
allow {
    input.tool_category == "DESTRUCTIVE"
    input.approved == true
}

# ── Internal helpers ─────────────────────────────────────────

_test_commands := {"pytest", "npm test", "cargo test", "go test", "jest", "vitest", "playwright"}

_is_test_command(cmd) {
    some t in _test_commands
    contains(lower(cmd), t)
}

_lint_commands := {"lint", "eslint", "ruff", "flake8", "mypy", "pylint", "black --check", "isort --check"}

_is_test_or_lint_command(cmd) {
    _is_test_command(cmd)
}

_is_test_or_lint_command(cmd) {
    some l in _lint_commands
    contains(lower(cmd), l)
}

# ── Deny reason ──────────────────────────────────────────────
deny_reason[msg] {
    not allow
    msg := sprintf("Tool '%s' blocked in phase '%s' (category: '%s')",
        [input.tool, input.phase, input.tool_category])
}
