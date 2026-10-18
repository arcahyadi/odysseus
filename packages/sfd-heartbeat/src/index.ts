/**
 * @agentos/sfd-heartbeat — Health Monitor
 * ADR-003 compliant plugin
 *
 * Health checking, uptime tracking, alerting.
 */

import type { SFDPlugin, PluginConfig, SFDPhase, PhaseContext, PhaseResult } from "../../types";

class HeartbeatMonitor {
  private endpoints: Map<string, { url: string; interval: number; lastOk: string | null; fails: number }> = new Map();
  private timers: Map<string, ReturnType<typeof setInterval>> = new Map();

  register(id: string, url: string, intervalMs: number = 30000) {
    this.endpoints.set(id, { url, interval: intervalMs, lastOk: null, fails: 0 });
  }

  unregister(id: string) {
    if (this.timers.has(id)) clearInterval(this.timers.get(id)!);
    this.endpoints.delete(id);
    this.timers.delete(id);
  }

  async check(id: string): Promise<boolean> {
    const ep = this.endpoints.get(id);
    if (!ep) return false;
    try {
      const resp = await fetch(ep.url);
      ep.lastOk = resp.ok ? new Date().toISOString() : ep.lastOk;
      ep.fails = resp.ok ? 0 : ep.fails + 1;
      return resp.ok;
    } catch {
      ep.fails++;
      return false;
    }
  }

  status(): Record<string, any> {
    const result: Record<string, any> = {};
    for (const [id, ep] of this.endpoints) result[id] = { ...ep, timers: undefined };
    return result;
  }
}

let instance: HeartbeatMonitor | null = null;
function getMonitor(): HeartbeatMonitor {
  if (!instance) instance = new HeartbeatMonitor();
  return instance;
}

export const plugin: SFDPlugin = {
  name: "sfd-heartbeat",
  version: "0.1.0",
  description: "Health checking, uptime tracking, alerting.",
  capabilities: [
    "heartbeat.check",
    "heartbeat.register",
    "heartbeat.status",
    "heartbeat.alert",
  ],

  async onActivate(config: PluginConfig) {
    // Start monitoring
  },

  async onDeactivate() {
    // Stop all timers
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
