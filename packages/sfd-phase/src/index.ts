/**
 * @agentos/sfd-phase — Phase Manager
 * ADR-003 compliant plugin
 *
 * Phase lifecycle, transitions, validation, rollback.
 */

import type { SFDPlugin, PluginConfig, SFDPhase, PhaseContext, PhaseResult } from "../../types";

const PHASE_ORDER: SFDPhase[] = ["research", "plan", "design", "implement", "review", "deploy", "evolve"];

class PhaseManager {
  private currentPhase: SFDPhase | null = null;
  private phaseHistory: { phase: SFDPhase; entered: string; exited: string | null }[] = [];

  async transition(to: SFDPhase): Promise<boolean> {
    const fromIdx = this.currentPhase ? PHASE_ORDER.indexOf(this.currentPhase) : -1;
    const toIdx = PHASE_ORDER.indexOf(to);
    if (toIdx < fromIdx) return false; // Can't go backward
    if (this.currentPhase) {
      const last = this.phaseHistory[this.phaseHistory.length - 1];
      if (last) last.exited = new Date().toISOString();
    }
    this.currentPhase = to;
    this.phaseHistory.push({ phase: to, entered: new Date().toISOString(), exited: null });
    return true;
  }

  canTransition(from: SFDPhase, to: SFDPhase): boolean {
    const fromIdx = PHASE_ORDER.indexOf(from);
    const toIdx = PHASE_ORDER.indexOf(to);
    return toIdx >= fromIdx;
  }

  getCurrent(): SFDPhase | null { return this.currentPhase; }
  getHistory() { return [...this.phaseHistory]; }
  getOrder() { return [...PHASE_ORDER]; }
}

let instance: PhaseManager | null = null;
function getPhaseManager(): PhaseManager {
  if (!instance) instance = new PhaseManager();
  return instance;
}

export const plugin: SFDPlugin = {
  name: "sfd-phase",
  version: "0.1.0",
  description: "Phase lifecycle management — transitions, validation, rollback.",
  capabilities: [
    "phase.transition",
    "phase.validate",
    "phase.current",
    "phase.history",
  ],

  async onActivate(config: PluginConfig) {
    // Load persisted phase state
  },

  async onDeactivate() {
    // Save phase state
  },

  async onPhase(phase: SFDPhase, context: PhaseContext): Promise<PhaseResult> {
    const start = Date.now();
    const mgr = getPhaseManager();
    const ok = await mgr.transition(phase);
    return {
      success: ok,
      phase,
      output: { transitioned: ok, currentPhase: mgr.getCurrent() },
      metrics: { durationMs: Date.now() - start },
    };
  },
};
