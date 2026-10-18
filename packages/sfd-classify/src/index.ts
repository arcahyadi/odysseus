/**
 * @agentos/sfd-classify — Classification Engine
 * ADR-003 compliant plugin
 *
 * Intent detection, event routing, content categorization.
 */

import type { SFDPlugin, PluginConfig, SFDPhase, PhaseContext, PhaseResult } from "../../types";

class Classifier {
  private categories: Map<string, string[]> = new Map();

  register(name: string, patterns: string[]) {
    this.categories.set(name, patterns);
  }

  classify(input: string): string[] {
    const matched: string[] = [];
    for (const [name, patterns] of this.categories) {
      if (patterns.some(p => input.toLowerCase().includes(p.toLowerCase()))) {
        matched.push(name);
      }
    }
    return matched;
  }
}

let instance: Classifier | null = null;
function getClassifier(): Classifier {
  if (!instance) instance = new Classifier();
  return instance;
}

export const plugin: SFDPlugin = {
  name: "sfd-classify",
  version: "0.1.0",
  description: "Intent classification, event routing, content categorization.",
  capabilities: [
    "classify.intent",
    "classify.content",
    "classify.route",
  ],

  async onActivate(config: PluginConfig) {
    // Load classification rules
  },

  async onDeactivate() {
    // Cleanup
  },

  async onPhase(phase: SFDPhase, context: PhaseContext): Promise<PhaseResult> {
    const start = Date.now();
    return {
      success: true,
      phase,
      output: { classified: true },
      metrics: { durationMs: Date.now() - start },
    };
  },
};
