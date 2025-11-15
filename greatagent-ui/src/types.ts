export type RunMode = "auto" | "human";

export type AgentCategory = "stem" | "tool" | "addon" | "database";

export interface AgentDefinition {
  id: string;
  label: string;
  description: string;
  type: AgentCategory;
  model?: string;
  implemented: boolean;
}

export interface GraphNode {
  id: string;
  label?: string;
  requires_human?: boolean;
  order?: number;
  type?: AgentCategory;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
}

export interface GraphBlueprint {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface WorkflowStep {
  agent: string;
  status: string;
  requires_human?: boolean;
  notes?: string;
}

export interface WorkflowSnapshot {
  mode: string;
  steps: WorkflowStep[];
  control_panel?: Record<string, unknown>;
  graph?: GraphBlueprint;
}

export type NodeStatus = "idle" | "ready" | "active" | "awaiting" | "completed" | "error";

export type NodeStatusMap = Record<string, NodeStatus>;

export interface SegmentRecord {
  input: Record<string, unknown>;
  output: Record<string, unknown>;
}

export interface AgentConfig {
  api_base: string;
  api_key: string;
  model: string;
  prompt: string;
}

export type AgentSettingsMap = Record<string, AgentConfig>;

export interface AgentErrorPayload {
  node: string;
  message: string;
  ts?: number;
}

export interface TraceSummary {
  id: string;
  name: string;
  status: string;
  url?: string;
}

export interface RunTraceMeta {
  trace_id: string;
  trace_url: string;
}
