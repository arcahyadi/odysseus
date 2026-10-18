---
name: sfd-decision-tree
description: Agent OS SFD v3.1 — complete decision tree per phase with agent, model, and tool assignments
---

# SFD Decision Tree

This skill defines the exact decision tree each agent follows per phase.

## Phase 1: CLASSIFY
- **Goal:** Understand the request, evaluate risk
- **Model:** deepseek-v4-pro
- **Decision tree:**
  1. Is this a project request? (contains "build", "create", "deploy"...)
     - NO → switch to CHAT mode (direct answer)
     - YES → continue
  2. Evaluate risk level:
     - Contains "delete", "rm", "format" → CRITICAL → ask human approval
     - Contains "deploy", "production", "database" → HIGH
     - Contains "refactor", "rewrite" → MEDIUM
     - Otherwise → LOW
  3. Call `sfd-phase({ action: "advance" })` to move to KNOW

## Phase 2: KNOW
- **Goal:** Gather context, search memory, load skills
- **Model:** deepseek-v4-pro
- **Agents:** @explore (for codebase search)
- **Decision tree:**
  1. Search memory for related past conversations
  2. Check if linguistic signals indicate past reference ("tu te souviens...")
  3. Load relevant skills from .opencode/skills/
  4. Call `sfd-phase({ action: "advance" })` to move to PLAN

## Phase 3: PLAN
- **Goal:** Decompose into objectives and tasks
- **Model:** deepseek-v4-pro
- **Agents:** @planner
- **Decision tree:**
  1. Is the task complex (>15 tools or >3 domains)?
     - YES → plan for multi-agent execution
     - NO → plan for single-agent execution
  2. Create objectives (2-4) with tasks per objective (1-3)
  3. Assign agent + model per task
  4. Emit plan as structured YAML
  5. Call `sfd-phase({ action: "advance" })` to move to BUILD

## Phase 4: BUILD
- **Goal:** Execute the plan with tools
- **Model:** minimax-m3 (code generation)
- **Agents:** @executor (multiple in parallel if needed)
- **Decision tree:**
  1. For each objective in the plan:
     a. Spawn @executor with the objective context
     b. Monitor progress (tools used, files created)
  2. If any executor fails → retry or escalate
  3. Call `sfd-phase({ action: "advance" })` to move to QUALITY

## Phase 5: QUALITY
- **Goal:** Verify, test, audit
- **Model:** deepseek-v4-pro
- **Agents:** @reviewer, @security-audit
- **Decision tree:**
  1. Run tests (if available)
  2. Run linter
  3. @reviewer audits code quality
  4. @security-audit checks for vulnerabilities
  5. If all pass → advance
  6. If failures → go back to BUILD (max 3 retries)
  7. Call `sfd-phase({ action: "advance" })` to move to AUTOEVAL

## Phase 6: AUTOEVAL
- **Goal:** Self-evaluate against success criteria
- **Model:** deepseek-v4-pro
- **Decision tree:**
  1. Did we achieve the original objective?
  2. Compare result vs plan (token usage, time, quality)
  3. Score the result (0-100%)
  4. If score < 70% → flag for improvement
  5. Call `sfd-phase({ action: "advance" })` to move to MEMORY_OBSERVE

## Phase 7: MEMORY_OBSERVE
- **Goal:** Learn and persist
- **Model:** deepseek-v4-pro
- **Decision tree:**
  1. Extract lessons learned (what worked, what didn't)
  2. Store facts with provenance:
     - [stated] for user-confirmed facts
     - [observed] for system-observed facts
  3. Update skill counters (aidant/nuisant)
  4. Classify stored data (public/internal/personal)
  5. Call `sfd-phase({ action: "complete" })`
