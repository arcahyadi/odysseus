/**
 * @agentos/sfd-discovery — Service Discovery
 * ADR-003 compliant plugin
 *
 * Service registry, endpoint probing, connector detection.
 */

import type { SFDPlugin, PluginConfig, SFDPhase, PhaseContext, PhaseResult } from "../../types";

class DiscoveryRegistry {
  private services: Map<string, { url: string; status: string; lastSeen: string }> = new Map();

  register(name: string, url: string) {
    this.services.set(name, { url, status: "unknown", lastSeen: new Date().toISOString() });
  }

  unregister(name: string) {
    this.services.delete(name);
  }

  list(): Record<string, any> {
    const result: Record<string, any> = {};
    for (const [name, info] of this.services) result[name] = info;
    return result;
  }

  async probe(name: string): Promise<boolean> {
    const svc = this.services.get(name);
    if (!svc) return false;
    try {
      const resp = await fetch(svc.url);
      svc.status = resp.ok ? "healthy" : "unhealthy";
      svc.lastSeen = new Date().toISOString();
      return resp.ok;
    } catch {
      svc.status = "down";
      return false;
    }
  }
}

let instance: DiscoveryRegistry | null = null;
function getRegistry(): DiscoveryRegistry {
  if (!instance) instance = new DiscoveryRegistry();
  return instance;
}

export const plugin: SFDPlugin = {
  name: "sfd-discovery",
  version: "0.1.0",
  description: "Service registry, endpoint probing, connector detection.",
  capabilities: [
    "discovery.register",
    "discovery.probe",
    "discovery.list",
    "discovery.unregister",
  ],

  async onActivate(config: PluginConfig) {
    // Load known services
  },

  async onDeactivate() {
    // Persist registry
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
