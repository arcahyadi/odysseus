/**
 * Shared types for all @agentos/sfd-* packages
 * ADR-003: Standard Plugin Interface
 */

/** SFD Phase identifiers */
export type SFDPhase =
  | "research"
  | "plan"
  | "design"
  | "implement"
  | "review"
  | "deploy"
  | "evolve";

/** Plugin configuration */
export interface PluginConfig {
  traceDir?: string;
  logLevel?: "debug" | "info" | "warn" | "error";
  [key: string]: any;
}

/** Phase execution context */
export interface PhaseContext {
  phase: SFDPhase;
  sessionId: string;
  projectId: string;
  traceId: string;
  payload: Record<string, any>;
  previousResults?: Record<string, any>;
}

/** Phase execution result */
export interface PhaseResult {
  success: boolean;
  phase: SFDPhase;
  output: Record<string, any>;
  metrics?: {
    durationMs: number;
    tokensUsed?: number;
    errors?: number;
  };
}

/** Standard SFD Plugin interface */
export interface SFDPlugin {
  readonly name: string;
  readonly version: string;
  readonly description: string;
  readonly capabilities: string[];

  onActivate(config: PluginConfig): Promise<void>;
  onDeactivate(): Promise<void>;
  onPhase(phase: SFDPhase, context: PhaseContext): Promise<PhaseResult>;
}

/** Event bus event structure */
export interface SFDEvent {
  event_id: string;
  timestamp: string;
  source: string;
  type: string;
  session_id: string;
  project_id: string;
  trace_id: string;
  data: Record<string, any>;
}
