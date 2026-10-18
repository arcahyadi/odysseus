/**
 * @agentos/sfd-security — Security Policy Engine
 * ADR-003 compliant plugin
 *
 * Content policy enforcement, injection detection, permission gating.
 */

import type { SFDPlugin, PluginConfig, SFDPhase, PhaseContext, PhaseResult } from "../../types";

class SecurityEngine {
  private blockedPatterns: string[] = [];

  addBlockedPattern(pattern: string) {
    this.blockedPatterns.push(pattern);
  }

  checkInjection(input: string): boolean {
    const dangerous = ["DROP TABLE", "rm -rf", "eval(", "exec("];
    return dangerous.some(d => input.toUpperCase().includes(d));
  }

  checkPolicy(content: string): { allowed: boolean; reason?: string } {
    for (const pattern of this.blockedPatterns) {
      if (content.includes(pattern)) {
        return { allowed: false, reason: `Blocked pattern: ${pattern}` };
      }
    }
    return { allowed: true };
  }
}

let instance: SecurityEngine | null = null;
function getSecurity(): SecurityEngine {
  if (!instance) instance = new SecurityEngine();
  return instance;
}

export const plugin: SFDPlugin = {
  name: "sfd-security",
  version: "0.1.0",
  description: "Content policy enforcement, injection detection, permission gating.",
  capabilities: [
    "security.scan",
    "security.policy",
    "security.injection-detect",
  ],

  async onActivate(config: PluginConfig) {
    // Load policy rules
  },

  async onDeactivate() {
    // Flush audit log
  },

  async onPhase(phase: SFDPhase, context: PhaseContext): Promise<PhaseResult> {
    const start = Date.now();
    const engine = getSecurity();
    // Auto-scan phase payload for injection
    const payloadStr = JSON.stringify(context.payload);
    if (engine.checkInjection(payloadStr)) {
      return {
        success: false,
        phase,
        output: { blocked: true, reason: "Injection detected in phase payload" },
        metrics: { durationMs: Date.now() - start },
      };
    }
    return {
      success: true,
      phase,
      output: { scanned: true },
      metrics: { durationMs: Date.now() - start },
    };
  },
};
