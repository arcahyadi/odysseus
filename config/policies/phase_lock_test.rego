# phase_lock_test.rego — Tests for phase_lock.rego transition rules.

package odysseus.phase_test

# ── Valid transitions ─────────────────────────────────────────

test_classify_to_know {
    allow_transition with input as {"from": "CLASSIFY", "to": "KNOW"}
}

test_classify_to_plan {
    allow_transition with input as {"from": "CLASSIFY", "to": "PLAN"}
}

test_classify_to_build {
    allow_transition with input as {"from": "CLASSIFY", "to": "BUILD"}
}

test_know_to_plan {
    allow_transition with input as {"from": "KNOW", "to": "PLAN"}
}

test_know_to_build {
    allow_transition with input as {"from": "KNOW", "to": "BUILD"}
}

test_plan_to_build {
    allow_transition with input as {"from": "PLAN", "to": "BUILD"}
}

test_plan_to_research {
    allow_transition with input as {"from": "PLAN", "to": "RESEARCH"}
}

test_build_to_quality {
    allow_transition with input as {"from": "BUILD", "to": "QUALITY"}
}

test_build_to_verify {
    allow_transition with input as {"from": "BUILD", "to": "VERIFY"}
}

test_quality_to_autoeval {
    allow_transition with input as {"from": "QUALITY", "to": "AUTOEVAL"}
}

test_quality_to_build {
    allow_transition with input as {"from": "QUALITY", "to": "BUILD"}
}

test_verify_to_autoeval {
    allow_transition with input as {"from": "VERIFY", "to": "AUTOEVAL"}
}

test_verify_to_build {
    allow_transition with input as {"from": "VERIFY", "to": "BUILD"}
}

test_autoeval_to_memory_observe {
    allow_transition with input as {"from": "AUTOEVAL", "to": "MEMORY_OBSERVE"}
}

test_autoeval_to_build {
    allow_transition with input as {"from": "AUTOEVAL", "to": "BUILD"}
}

test_memory_observe_to_classify {
    allow_transition with input as {"from": "MEMORY_OBSERVE", "to": "CLASSIFY"}
}

test_memory_observe_to_build {
    allow_transition with input as {"from": "MEMORY_OBSERVE", "to": "BUILD"}
}

test_research_to_plan {
    allow_transition with input as {"from": "RESEARCH", "to": "PLAN"}
}

test_research_to_build {
    allow_transition with input as {"from": "RESEARCH", "to": "BUILD"}
}

test_innovate_to_plan {
    allow_transition with input as {"from": "INNOVATE", "to": "PLAN"}
}

test_innovate_to_build {
    allow_transition with input as {"from": "INNOVATE", "to": "BUILD"}
}

# ── Emergency escape: any phase → BUILD ──────────────────────

test_classify_to_build_escape {
    allow_transition with input as {"from": "CLASSIFY", "to": "BUILD"}
}

# ── Invalid transitions ──────────────────────────────────────

test_know_to_autoeval_blocked {
    not allow_transition with input as {"from": "KNOW", "to": "AUTOEVAL"}
}

test_plan_to_memory_observe_blocked {
    not allow_transition with input as {"from": "PLAN", "to": "MEMORY_OBSERVE"}
}

test_build_to_classify_blocked {
    not allow_transition with input as {"from": "BUILD", "to": "CLASSIFY"}
}

test_autoeval_to_plan_blocked {
    not allow_transition with input as {"from": "AUTOEVAL", "to": "PLAN"}
}

test_memory_observe_to_quality_blocked {
    not allow_transition with input as {"from": "MEMORY_OBSERVE", "to": "QUALITY"}
}

# ── Deny reason ──────────────────────────────────────────────

test_deny_reason_for_invalid_transition {
    count(deny_reason) > 0 with input as {"from": "KNOW", "to": "AUTOEVAL"}
}

# ── Valid phase set ──────────────────────────────────────────

test_valid_phases_all_present {
    valid_transition["CLASSIFY"]
    valid_transition["KNOW"]
    valid_transition["PLAN"]
    valid_transition["BUILD"]
    valid_transition["QUALITY"]
    valid_transition["VERIFY"]
    valid_transition["AUTOEVAL"]
    valid_transition["MEMORY_OBSERVE"]
    valid_transition["RESEARCH"]
    valid_transition["INNOVATE"]
}
