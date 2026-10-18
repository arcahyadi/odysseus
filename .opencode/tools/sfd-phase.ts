/**
 * SFD Phase System — Custom tool for OpenCode
 *
 * Implements 7-phase decision tree: CLASSIFY→KNOW→PLAN→BUILD→QUALITY→AUTOEVAL→MEMORY
 * Each agent must call this tool to advance phases.
 * The tool enforces: you can't skip phases, you can't go backwards.
 *
 * Usage by the agent:
 *   sfd-phase({ action: "advance", current: "PLAN" })
 *   → returns: { allowed: true, new_phase: "BUILD", required_agents: ["executor"] }
 *
 *   sfd-phase({ action: "advance", current: "CLASSIFY" })
 *   → returns: { allowed: false, reason: "Complete risk assessment before KNOW" }
 */

import { tool } from "@opencode-ai/plugin"

const PHASES = ["CLASSIFY", "KNOW", "PLAN", "BUILD", "QUALITY", "AUTOEVAL", "MEMORY_OBSERVE"];

const PHASE_REQUIREMENTS = {
  CLASSIFY: { required: [], agents: [], model: "opencode/deepseek-v4-pro" },
  KNOW:     { required: ["risk_assessed"], agents: ["explore"], model: "opencode/deepseek-v4-pro" },
  PLAN:     { required: ["memory_searched"], agents: ["planner"], model: "opencode/deepseek-v4-pro" },
  BUILD:    { required: ["plan_created"], agents: ["executor"], model: "opencode/minimax-m3" },
  QUALITY:  { required: ["code_written"], agents: ["reviewer"], model: "opencode/deepseek-v4-pro" },
  AUTOEVAL: { required: ["quality_checked"], agents: [], model: "opencode/deepseek-v4-pro" },
  MEMORY_OBSERVE: { required: ["evaluation_done"], agents: [], model: "opencode/deepseek-v4-pro" },
};

// In-memory state (per session, resets on restart)
const sessionPhases = new Map();

export default tool({
  description: "SFD Phase manager — advance through the 7-phase pipeline. Call this before starting work in each phase. Returns whether the phase transition is allowed and what agents/models to use.",
  args: {
    action: tool.schema.enum(["advance", "status", "complete"]).describe("Action: advance to next phase, check current status, or mark complete"),
    session_id: tool.schema.string().optional().describe("Session identifier for state tracking"),
  },
  async execute(args, context) {
    const sid = args.session_id || context.sessionID || "default";

    if (!sessionPhases.has(sid)) {
      sessionPhases.set(sid, { phase: "CLASSIFY", completed: [], requirements: {} });
    }

    const state = sessionPhases.get(sid);

    if (args.action === "status") {
      const reqs = PHASE_REQUIREMENTS[state.phase];
      return JSON.stringify({
        current_phase: state.phase,
        phase_index: PHASES.indexOf(state.phase) + 1,
        total_phases: 7,
        completed_phases: state.completed,
        required_for_next: reqs.required,
        recommended_agents: reqs.agents,
        recommended_model: reqs.model,
      });
    }

    if (args.action === "complete") {
      state.completed.push(state.phase);
      state.phase = "DONE";
      sessionPhases.set(sid, state);
      return JSON.stringify({
        status: "complete",
        phases_completed: state.completed,
        message: `All phases completed: ${state.completed.join(" -> ")}`,
      });
    }

    if (args.action === "advance") {
      const currentIdx = PHASES.indexOf(state.phase);
      if (currentIdx === -1) {
        return JSON.stringify({ allowed: false, reason: `Unknown phase: ${state.phase}` });
      }

      // Check requirements
      const reqs = PHASE_REQUIREMENTS[state.phase];
      const missing = reqs.required.filter(r => !state.requirements[r]);
      if (missing.length > 0) {
        return JSON.stringify({
          allowed: false,
          current_phase: state.phase,
          reason: `Missing requirements for ${state.phase}: ${missing.join(", ")}`,
          what_to_do: `Complete these checks before advancing`,
        });
      }

      // Advance
      state.completed.push(state.phase);
      const newIdx = currentIdx + 1;
      if (newIdx >= PHASES.length) {
        state.phase = "DONE";
        return JSON.stringify({ allowed: true, status: "all_complete", phases: state.completed });
      }

      state.phase = PHASES[newIdx];
      const newReqs = PHASE_REQUIREMENTS[state.phase];
      sessionPhases.set(sid, state);

      return JSON.stringify({
        allowed: true,
        new_phase: state.phase,
        phase_index: newIdx + 1,
        total_phases: 7,
        required_checks: newReqs.required,
        recommended_agents: newReqs.agents,
        recommended_model: newReqs.model,
        progress: state.completed.map(p => `${p} ✓`).join(" -> "),
      });
    }
  },
});

/**
 * PLUGIN HOOK — Enforces phase discipline
 *
 * Hooks into tool.execute.before to prevent tools from running
 * in wrong phases. For example: no file writes during PLAN phase.
 */
export const SFDPhasePlugin = async (ctx) => {
  return {
    "tool.execute.before": async (input, output) => {
      const sid = input.sessionID || "default";
      const state = sessionPhases.get(sid);
      if (!state) return; // No phase tracking

      const phase = state.phase;
      const tool = input.tool;

      // Enforce: no writes during PLAN phase
      if (phase === "PLAN" && ["write", "edit", "apply_patch"].includes(tool)) {
        throw new Error(`SFD Phase lock: Cannot ${tool} during PLAN phase. Advance to BUILD first.`);
      }

      // Enforce: no bash during CLASSIFY
      if (phase === "CLASSIFY" && tool === "bash") {
        throw new Error("SFD Phase lock: Cannot execute commands during CLASSIFY. Complete risk assessment first.");
      }
    },
  };
};
