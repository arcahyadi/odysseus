# phase_lock.rego — Phase transition authorization for Odysseus canonical loop.
# Only valid forward transitions are allowed. Rejected transitions are logged.

package odysseus.phase

default allow_transition = false

# ── Valid transitions (canonical sequence) ────────────────────
# CLASSIFY → KNOW
allow_transition {
    input.from == "CLASSIFY"
    input.to == "KNOW"
}

# CLASSIFY → BUILD (shortcut: low-risk tasks skip planning)
allow_transition {
    input.from == "CLASSIFY"
    input.to == "BUILD"
}

# CLASSIFY → PLAN
allow_transition {
    input.from == "CLASSIFY"
    input.to == "PLAN"
}

# KNOW → PLAN
allow_transition {
    input.from == "KNOW"
    input.to == "PLAN"
}

# KNOW → BUILD (shortcut: knowledge retrieval → direct implementation)
allow_transition {
    input.from == "KNOW"
    input.to == "BUILD"
}

# PLAN → BUILD
allow_transition {
    input.from == "PLAN"
    input.to == "BUILD"
}

# PLAN → RESEARCH (need more info before building)
allow_transition {
    input.from == "PLAN"
    input.to == "RESEARCH"
}

# BUILD → QUALITY
allow_transition {
    input.from == "BUILD"
    input.to == "QUALITY"
}

# BUILD → VERIFY (skip quality, go straight to verification)
allow_transition {
    input.from == "BUILD"
    input.to == "VERIFY"
}

# QUALITY → AUTOEVAL
allow_transition {
    input.from == "QUALITY"
    input.to == "AUTOEVAL"
}

# QUALITY → BUILD (quality check failed, back to implementation)
allow_transition {
    input.from == "QUALITY"
    input.to == "BUILD"
}

# VERIFY → AUTOEVAL
allow_transition {
    input.from == "VERIFY"
    input.to == "AUTOEVAL"
}

# VERIFY → BUILD (verification failed, back to implementation)
allow_transition {
    input.from == "VERIFY"
    input.to == "BUILD"
}

# AUTOEVAL → MEMORY_OBSERVE
allow_transition {
    input.from == "AUTOEVAL"
    input.to == "MEMORY_OBSERVE"
}

# AUTOEVAL → BUILD (autoeval found issues, back to implementation)
allow_transition {
    input.from == "AUTOEVAL"
    input.to == "BUILD"
}

# MEMORY_OBSERVE → CLASSIFY (new task in same session)
allow_transition {
    input.from == "MEMORY_OBSERVE"
    input.to == "CLASSIFY"
}

# MEMORY_OBSERVE → BUILD (session continues with new task)
allow_transition {
    input.from == "MEMORY_OBSERVE"
    input.to == "BUILD"
}

# ── Legacy phase shortcuts ───────────────────────────────────
# RESEARCH → PLAN
allow_transition {
    input.from == "RESEARCH"
    input.to == "PLAN"
}

# RESEARCH → BUILD
allow_transition {
    input.from == "RESEARCH"
    input.to == "BUILD"
}

# INNOVATE → PLAN
allow_transition {
    input.from == "INNOVATE"
    input.to == "PLAN"
}

# INNOVATE → BUILD
allow_transition {
    input.from == "INNOVATE"
    input.to == "BUILD"
}

# ── Any phase → BUILD (emergency escape hatch) ──────────────
allow_transition {
    input.to == "BUILD"
    _is_valid_phase(input.from)
}

# ── Helpers ──────────────────────────────────────────────────

_valid_phases := {"CLASSIFY", "KNOW", "PLAN", "BUILD", "QUALITY",
                   "VERIFY", "AUTOEVAL", "MEMORY_OBSERVE",
                   "RESEARCH", "INNOVATE"}

_is_valid_phase(phase) {
    _valid_phases[phase]
}

# ── Deny reason ──────────────────────────────────────────────
deny_reason[msg] {
    not allow_transition
    msg := sprintf("Invalid transition: '%s' → '%s'", [input.from, input.to])
}

# ── Transition validation helper ─────────────────────────────
valid_transition[phase] {
    _valid_phases[phase]
}
