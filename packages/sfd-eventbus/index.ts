/**
 * SFD Central Event Bus — Plugin OpenCode
 *
 * 15 families, 62 event types. Covers all master reference files:
 * - 01-SFD: 22 principes, 20 modules
 * - 02-OUTILS: 60 outils, 5 couches
 * - 03-OBJECTIFS: architecture plugins
 * - 04-COUVERTURE: 8 axes
 *
 * Every action, decision, error emits a structured event.
 * Consumers: Cockpit UI, Chat UI, Traces JSONL, LangFuse, Alerts, Plugins.
 */

import { tool } from "@opencode-ai/plugin"
import * as fs from "fs"
import * as path from "path"

// ============================================================================
// Event Types (15 families)
// ============================================================================
const EVENT_FAMILIES = {
  phase:    ["phase_enter", "phase_exit", "phase_skip", "phase_error"],
  tool:     ["tool_start", "tool_output", "tool_error", "tool_blocked", "tool_retry"],
  agent:    ["agent_spawn", "agent_result", "agent_error", "agent_dispatch", "agent_sub_spawn"],
  model:    ["model_selected", "model_fallback", "model_error", "model_metrics"],
  memory:   ["memory_read", "memory_write", "memory_omitted", "memory_conflict", "memory_classified"],
  budget:   ["budget_updated", "budget_warning", "budget_exceeded"],
  security: ["injection_detected", "content_blocked", "destructive_blocked", "permission_denied"],
  workflow: ["workflow_start", "workflow_step_complete", "workflow_step_retry", "workflow_saga_compensate", "workflow_approval_needed", "workflow_approval_resolved"],
  discovery:["discovery_search", "registry_found", "connector_suggested", "connector_connected"],
  search:   ["signal_detected", "conversation_search", "past_context_loaded"],
  session:  ["session_created", "session_compacted", "session_saved", "session_error"],
  system:   ["startup", "shutdown", "health_change", "error"],
  user:     ["message_sent", "preference_updated", "preference_blocked", "feedback_given"],
  preference:["prefs_loaded", "prefs_resolved", "prefs_injected"],
  mcp:      ["mcp_connected", "mcp_disconnected", "mcp_tool_registered", "mcp_error"],
};

// ============================================================================
// Subscribers
// ============================================================================
type EventHandler = (event: any) => void;
const subscribers: Map<string, EventHandler[]> = new Map();

// ============================================================================
// Event Bus Core
// ============================================================================
class EventBus {
  private traceDir: string;
  private buffer: any[] = [];
  private flushInterval: any;

  constructor(traceDir: string = "data/traces") {
    this.traceDir = traceDir;
    if (!fs.existsSync(traceDir)) fs.mkdirSync(traceDir, { recursive: true });
    // Flush to JSONL every 5 seconds
    this.flushInterval = setInterval(() => this.flush(), 5000);
  }

  /** Emit an event. All subscribers of matching type are called. */
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

    // Notify subscribers
    const handlers = subscribers.get(type) || [];
    for (const handler of handlers) {
      try { handler(event); } catch (e) { /* never crash on subscriber error */ }
    }

    // Also notify wildcard subscribers
    const wildcard = subscribers.get("*") || [];
    for (const handler of wildcard) {
      try { handler(event); } catch (e) {}
    }

    // Buffer for JSONL
    this.buffer.push(event);
    if (this.buffer.length > 100) this.flush();

    return event;
  }

  /** Subscribe to a specific event type. Use "*" for all events. */
  on(type: string, handler: EventHandler) {
    if (!subscribers.has(type)) subscribers.set(type, []);
    subscribers.get(type)!.push(handler);
  }

  /** Flush buffered events to JSONL file */
  private flush() {
    if (this.buffer.length === 0) return;
    const today = new Date().toISOString().slice(0, 10);
    const file = path.join(this.traceDir, `events-${today}.jsonl`);
    const lines = this.buffer.map(e => JSON.stringify(e)).join("\n") + "\n";
    fs.appendFileSync(file, lines);
    this.buffer = [];
  }

  /** Get event family info */
  getFamilies() { return EVENT_FAMILIES; }

  /** Count total event types */
  getTypeCount() {
    return Object.values(EVENT_FAMILIES).reduce((sum, types) => sum + types.length, 0);
  }
}

// Singleton
let bus: EventBus | null = null;

function getBus(): EventBus {
  if (!bus) bus = new EventBus();
  return bus;
}

// ============================================================================
// Plugin: SFD Event Bus
// ============================================================================
export const SFDEventBusPlugin = async (ctx: any) => {
  const b = getBus();

  // Log startup
  b.emit("system", "startup", {
    version: "1.0.0",
    families: Object.keys(EVENT_FAMILIES).length,
    event_types: b.getTypeCount(),
  });

  return {
    "tool.execute.after": async (input: any, output: any) => {
      b.emit("tool", "tool_output", {
        tool_name: input.tool,
        exit_code: output.exit_code || 0,
        duration_ms: Date.now() - (input._startTime || Date.now()),
        session_id: input.sessionID,
      });
    },
    "session.created": async (input: any) => {
      b.emit("session", "session_created", { session_id: input.sessionID });
    },
    "session.error": async (input: any) => {
      b.emit("session", "session_error", { session_id: input.sessionID, error: input.error });
    },
  };
};

// ============================================================================
// Custom Tool: sfd-event — query the event bus
// ============================================================================
export default tool({
  description: "SFD Event Bus — emit or query events. 15 families, 62 types. Use this to track everything happening in the system.",
  args: {
    action: tool.schema.enum(["emit", "stats"]).describe("Emit an event or get stats"),
    source: tool.schema.string().optional().describe("Event source family (phase, tool, agent, model, memory, budget, security, workflow, discovery, search, session, system, user, preference, mcp)"),
    type: tool.schema.string().optional().describe("Event type (e.g., phase_enter, tool_start, agent_spawn)"),
    data: tool.schema.string().optional().describe("JSON string of event data"),
  },
  async execute(args: any, context: any) {
    const b = getBus();

    if (args.action === "stats") {
      return JSON.stringify({
        families: Object.keys(EVENT_FAMILIES).length,
        event_types: b.getTypeCount(),
        families_detail: EVENT_FAMILIES,
      });
    }

    if (args.action === "emit" && args.source && args.type) {
      const data = args.data ? JSON.parse(args.data) : {};
      data.session_id = context.sessionID;
      const event = b.emit(args.source, args.type, data);
      return JSON.stringify({ emitted: true, event_id: event.event_id });
    }

    return JSON.stringify({ error: "Invalid action. Use 'stats' or 'emit' with source+type." });
  },
});
