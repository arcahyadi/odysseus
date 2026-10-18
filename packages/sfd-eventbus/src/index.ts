/**
 * @agentos/sfd-eventbus — Central Event Bus
 * ADR-003 compliant plugin
 *
 * 15 families, 62 event types. Tracks all pipeline activity.
 */

import type { SFDPlugin, PluginConfig, SFDPhase, PhaseContext, PhaseResult } from "../../types";
import * as fs from "fs";
import * as path from "path";

// ============================================================================
// Event Types (15 families)
// ============================================================================
const EVENT_FAMILIES: Record<string, string[]> = {
  phase:     ["phase_enter", "phase_exit", "phase_skip", "phase_error"],
  tool:      ["tool_start", "tool_output", "tool_error", "tool_blocked", "tool_retry"],
  agent:     ["agent_spawn", "agent_result", "agent_error", "agent_dispatch", "agent_sub_spawn"],
  model:     ["model_selected", "model_fallback", "model_error", "model_metrics"],
  memory:    ["memory_read", "memory_write", "memory_omitted", "memory_conflict", "memory_classified"],
  budget:    ["budget_updated", "budget_warning", "budget_exceeded"],
  security:  ["injection_detected", "content_blocked", "destructive_blocked", "permission_denied"],
  workflow:  ["workflow_start", "workflow_step_complete", "workflow_step_retry", "workflow_saga_compensate", "workflow_approval_needed", "workflow_approval_resolved"],
  discovery: ["discovery_search", "registry_found", "connector_suggested", "connector_connected"],
  search:    ["signal_detected", "conversation_search", "past_context_loaded"],
  session:   ["session_created", "session_compacted", "session_saved", "session_error"],
  system:    ["startup", "shutdown", "health_change", "error"],
  user:      ["message_sent", "preference_updated", "preference_blocked", "feedback_given"],
  preference:["prefs_loaded", "prefs_resolved", "prefs_injected"],
  mcp:       ["mcp_connected", "mcp_disconnected", "mcp_tool_registered", "mcp_error"],
};

type EventHandler = (event: any) => void;
const subscribers: Map<string, EventHandler[]> = new Map();

class EventBus {
  private traceDir: string;
  private buffer: any[] = [];
  private flushInterval: ReturnType<typeof setInterval> | null = null;
  private logLevel: string = "info";

  constructor(traceDir: string = "data/traces") {
    this.traceDir = traceDir;
    if (!fs.existsSync(traceDir)) fs.mkdirSync(traceDir, { recursive: true });
  }

  emit(source: string, type: string, data: Record<string, any> = {}) {
    const event = {
      event_id: crypto.randomUUID?.() || Math.random().toString(36).slice(2),
      timestamp: new Date().toISOString(),
      source,
      type,
      session_id: data.session_id || "",
      project_id: data.project_id || "",
      trace_id: data.trace_id || "",
      data,
    };

    const handlers = subscribers.get(type) || [];
    for (const handler of handlers) { try { handler(event); } catch {} }

    const wildcard = subscribers.get("*") || [];
    for (const handler of wildcard) { try { handler(event); } catch {} }

    this.buffer.push(event);
    if (this.buffer.length > 100) this.flush();
    return event;
  }

  on(type: string, handler: EventHandler) {
    if (!subscribers.has(type)) subscribers.set(type, []);
    subscribers.get(type)!.push(handler);
  }

  private flush() {
    if (this.buffer.length === 0) return;
    const today = new Date().toISOString().slice(0, 10);
    const file = path.join(this.traceDir, `events-${today}.jsonl`);
    const lines = this.buffer.map(e => JSON.stringify(e)).join("\n") + "\n";
    fs.appendFileSync(file, lines);
    this.buffer = [];
  }

  getFamilies() { return EVENT_FAMILIES; }
  getTypeCount() { return Object.values(EVENT_FAMILIES).reduce((sum, types) => sum + types.length, 0); }
}

let bus: EventBus | null = null;
function getBus(): EventBus {
  if (!bus) bus = new EventBus();
  return bus;
}

// ============================================================================
// Plugin: SFD Event Bus (ADR-003 compliant)
// ============================================================================
export const plugin: SFDPlugin = {
  name: "sfd-eventbus",
  version: "1.1.0",
  description: "Central event bus — 15 families, 62 events. Tracks all pipeline activity.",
  capabilities: [
    "eventbus.emit",
    "eventbus.subscribe",
    "eventbus.trace",
    "eventbus.stats",
  ],

  async onActivate(config: PluginConfig) {
    const b = getBus();
    if (config.traceDir) (b as any).traceDir = config.traceDir;
    if (config.logLevel) (b as any).logLevel = config.logLevel;
    b.emit("system", "startup", {
      version: this.version,
      families: Object.keys(EVENT_FAMILIES).length,
      event_types: b.getTypeCount(),
    });
    // Start flush interval
    (b as any).flushInterval = setInterval(() => b["flush"], 5000);
  },

  async onDeactivate() {
    const b = getBus();
    if ((b as any).flushInterval) clearInterval((b as any).flushInterval);
    (b as any).flush();
    b.emit("system", "shutdown", {});
  },

  async onPhase(phase: SFDPhase, context: PhaseContext): Promise<PhaseResult> {
    const b = getBus();
    const start = Date.now();
    b.emit("phase", "phase_enter", {
      phase,
      session_id: context.sessionId,
      project_id: context.projectId,
    });
    // EventBus phase is passive: just logs and tracks
    return {
      success: true,
      phase,
      output: { tracked: true },
      metrics: { durationMs: Date.now() - start },
    };
  },
};
