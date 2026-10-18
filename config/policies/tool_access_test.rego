# tool_access_test.rego — Tests for tool_access.rego phase-aware policies.

package odysseus.tool_test

import future.keywords.in

# ── BUILD phase ──────────────────────────────────────────────

test_build_allows_write {
    allow with input as {
        "phase": "BUILD",
        "tool": "write_file",
        "tool_category": "WRITE"
    }
}

test_build_allows_destructive_tool {
    allow with input as {
        "phase": "BUILD",
        "tool": "delete_file",
        "tool_category": "DESTRUCTIVE",
        "approved": false
    }
}

test_build_allows_exec {
    allow with input as {
        "phase": "BUILD",
        "tool": "bash",
        "tool_category": "EXEC",
        "command": "rm -rf /tmp/test"
    }
}

test_build_allows_read {
    allow with input as {
        "phase": "BUILD",
        "tool": "read_file",
        "tool_category": "READ"
    }
}

# ── PLAN phase ───────────────────────────────────────────────

test_plan_allows_read {
    allow with input as {
        "phase": "PLAN",
        "tool": "read_file",
        "tool_category": "READ"
    }
}

test_plan_allows_search {
    allow with input as {
        "phase": "PLAN",
        "tool": "grep",
        "tool_category": "SEARCH"
    }
}

test_plan_allows_draft {
    allow with input as {
        "phase": "PLAN",
        "tool": "write_file",
        "tool_category": "DRAFT"
    }
}

test_plan_blocks_exec {
    not allow with input as {
        "phase": "PLAN",
        "tool": "bash",
        "tool_category": "EXEC",
        "command": "pytest tests/"
    }
}

test_plan_allows_write_to_planning {
    allow with input as {
        "phase": "PLAN",
        "tool": "write_file",
        "tool_category": "WRITE",
        "write_path": ".planning/PLAN.md"
    }
}

test_plan_allows_write_to_process {
    allow with input as {
        "phase": "PLAN",
        "tool": "write_file",
        "tool_category": "WRITE",
        "write_path": "process/spec.md"
    }
}

test_plan_blocks_write_to_src {
    not allow with input as {
        "phase": "PLAN",
        "tool": "edit_file",
        "tool_category": "WRITE",
        "write_path": "src/main.py"
    }
}

# ── CLASSIFY phase ───────────────────────────────────────────

test_classify_allows_read {
    allow with input as {
        "phase": "CLASSIFY",
        "tool": "read_file",
        "tool_category": "READ"
    }
}

test_classify_allows_search {
    allow with input as {
        "phase": "CLASSIFY",
        "tool": "grep",
        "tool_category": "SEARCH"
    }
}

test_classify_blocks_write {
    not allow with input as {
        "phase": "CLASSIFY",
        "tool": "write_file",
        "tool_category": "WRITE"
    }
}

test_classify_blocks_exec {
    not allow with input as {
        "phase": "CLASSIFY",
        "tool": "bash",
        "tool_category": "EXEC"
    }
}

# ── KNOW phase ───────────────────────────────────────────────

test_know_allows_read {
    allow with input as {
        "phase": "KNOW",
        "tool": "read_file",
        "tool_category": "READ"
    }
}

test_know_allows_search {
    allow with input as {
        "phase": "KNOW",
        "tool": "grep",
        "tool_category": "SEARCH"
    }
}

test_know_allows_knowledge {
    allow with input as {
        "phase": "KNOW",
        "tool": "cbm_search",
        "tool_category": "KNOWLEDGE"
    }
}

test_know_blocks_write {
    not allow with input as {
        "phase": "KNOW",
        "tool": "edit_file",
        "tool_category": "WRITE"
    }
}

test_know_blocks_exec {
    not allow with input as {
        "phase": "KNOW",
        "tool": "bash",
        "tool_category": "EXEC"
    }
}

# ── RESEARCH phase ───────────────────────────────────────────

test_research_allows_read {
    allow with input as {
        "phase": "RESEARCH",
        "tool": "read_file",
        "tool_category": "READ"
    }
}

test_research_allows_search {
    allow with input as {
        "phase": "RESEARCH",
        "tool": "grep",
        "tool_category": "SEARCH"
    }
}

test_research_blocks_write {
    not allow with input as {
        "phase": "RESEARCH",
        "tool": "write_file",
        "tool_category": "WRITE"
    }
}

# ── INNOVATE phase ───────────────────────────────────────────

test_innovate_allows_read {
    allow with input as {
        "phase": "INNOVATE",
        "tool": "read_file",
        "tool_category": "READ"
    }
}

test_innovate_allows_draft {
    allow with input as {
        "phase": "INNOVATE",
        "tool": "write_file",
        "tool_category": "DRAFT"
    }
}

test_innovate_blocks_exec {
    not allow with input as {
        "phase": "INNOVATE",
        "tool": "bash",
        "tool_category": "EXEC"
    }
}

# ── VERIFY phase ─────────────────────────────────────────────

test_verify_allows_read {
    allow with input as {
        "phase": "VERIFY",
        "tool": "read_file",
        "tool_category": "READ"
    }
}

test_verify_allows_test_exec {
    allow with input as {
        "phase": "VERIFY",
        "tool": "bash",
        "tool_category": "EXEC",
        "command": "pytest tests/"
    }
}

test_verify_allows_npm_test {
    allow with input as {
        "phase": "VERIFY",
        "tool": "bash",
        "tool_category": "EXEC",
        "command": "npm test"
    }
}

test_verify_blocks_non_test_exec {
    not allow with input as {
        "phase": "VERIFY",
        "tool": "bash",
        "tool_category": "EXEC",
        "command": "rm -rf dist/"
    }
}

test_verify_blocks_write {
    not allow with input as {
        "phase": "VERIFY",
        "tool": "edit_file",
        "tool_category": "WRITE"
    }
}

# ── QUALITY phase ────────────────────────────────────────────

test_quality_allows_read {
    allow with input as {
        "phase": "QUALITY",
        "tool": "read_file",
        "tool_category": "READ"
    }
}

test_quality_allows_test_exec {
    allow with input as {
        "phase": "QUALITY",
        "tool": "bash",
        "tool_category": "EXEC",
        "command": "pytest tests/"
    }
}

test_quality_allows_lint {
    allow with input as {
        "phase": "QUALITY",
        "tool": "bash",
        "tool_category": "EXEC",
        "command": "ruff check src/"
    }
}

test_quality_blocks_non_test_exec {
    not allow with input as {
        "phase": "QUALITY",
        "tool": "bash",
        "tool_category": "EXEC",
        "command": "pip install requests"
    }
}

# ── AUTOEVAL phase ───────────────────────────────────────────

test_autoeval_allows_exec {
    allow with input as {
        "phase": "AUTOEVAL",
        "tool": "bash",
        "tool_category": "EXEC",
        "command": "python eval.py"
    }
}

test_autoeval_allows_write {
    allow with input as {
        "phase": "AUTOEVAL",
        "tool": "edit_file",
        "tool_category": "WRITE"
    }
}

# ── MEMORY_OBSERVE phase ─────────────────────────────────────

test_memory_observe_allows_write {
    allow with input as {
        "phase": "MEMORY_OBSERVE",
        "tool": "write_file",
        "tool_category": "WRITE"
    }
}

test_memory_observe_allows_read {
    allow with input as {
        "phase": "MEMORY_OBSERVE",
        "tool": "read_file",
        "tool_category": "READ"
    }
}

# ── Destructive tool approval ────────────────────────────────

test_destructive_blocked_without_approval {
    not allow with input as {
        "phase": "BUILD",
        "tool": "delete_file",
        "tool_category": "DESTRUCTIVE",
        "approved": false
    }
}

test_destructive_allowed_with_approval {
    allow with input as {
        "phase": "BUILD",
        "tool": "delete_file",
        "tool_category": "DESTRUCTIVE",
        "approved": true
    }
}

# ── Default deny ─────────────────────────────────────────────

test_unknown_phase_blocked {
    not allow with input as {
        "phase": "UNKNOWN_PHASE",
        "tool": "bash",
        "tool_category": "EXEC"
    }
}

# ── Deny reason ──────────────────────────────────────────────

test_deny_reason_produced {
    count(deny_reason) > 0 with input as {
        "phase": "KNOW",
        "tool": "bash",
        "tool_category": "EXEC"
    }
}
