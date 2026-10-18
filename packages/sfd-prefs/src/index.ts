/**
 * @agentos/sfd-prefs — Preferences Manager
 * ADR-003 compliant plugin
 *
 * Layered preference resolution: user → session → project → defaults.
 * Supports constraints injection.
 */

import type { SFDPlugin, PluginConfig, SFDPhase, PhaseContext, PhaseResult } from "../../types";

class PrefsManager {
  private layers: Map<string, Map<string, any>> = new Map();

  constructor() {
    this.layers.set("defaults", new Map());
    this.layers.set("project", new Map());
    this.layers.set("session", new Map());
    this.layers.set("user", new Map());
  }

  set(layer: string, key: string, value: any) {
    if (!this.layers.has(layer)) this.layers.set(layer, new Map());
    this.layers.get(layer)!.set(key, value);
  }

  get(key: string): any {
    const order = ["user", "session", "project", "defaults"];
    for (const layer of order) {
      const map = this.layers.get(layer);
      if (map && map.has(key)) return map.get(key);
    }
    return undefined;
  }
}

let instance: PrefsManager | null = null;
function getPrefs(): PrefsManager {
  if (!instance) instance = new PrefsManager();
  return instance;
}

export const plugin: SFDPlugin = {
  name: "sfd-prefs",
  version: "0.1.0",
  description: "Layered preference management with resolution and injection.",
  capabilities: [
    "prefs.get",
    "prefs.set",
    "prefs.resolve",
    "prefs.inject",
  ],

  async onActivate(config: PluginConfig) {
    // Load defaults
  },

  async onDeactivate() {
    // Persist user prefs
  },

  async onPhase(phase: SFDPhase, context: PhaseContext): Promise<PhaseResult> {
    const start = Date.now();
    return {
      success: true,
      phase,
      output: {},
      metrics: { durationMs: Date.now() - start },
    };
  },
};
