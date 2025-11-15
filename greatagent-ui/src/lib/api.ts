import { API_BASE } from "../config";
import type { AgentSettingsMap, GraphBlueprint, RunMode, TraceSummary } from "../types";

const jsonHeaders = { "Content-Type": "application/json" };

const apiFetch = async <T>(path: string, init?: RequestInit) => {
  const url = `${API_BASE}${path}`;
  const resp = await fetch(url, init);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || resp.statusText);
  }
  if (resp.status === 204) {
    return undefined as T;
  }
  return (await resp.json()) as T;
};

export const startRun = (user_query: string, mode: RunMode, workflow_override?: string[]) =>
  apiFetch<{ run_id: string }>("/run", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ user_query, mode, workflow_override }),
  });

export const pauseRun = (runId: string) =>
  apiFetch(`/pause/${runId}`, { method: "POST" });

export const resumeRun = (runId: string) =>
  apiFetch(`/resume/${runId}`, { method: "POST" });

export const stopRun = (runId: string) =>
  apiFetch(`/stop/${runId}`, { method: "POST" });

export const submitSelection = (run_id: string, node: string, choice_index: number) =>
  apiFetch("/select", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ run_id, node, choice_index }),
  });

export const saveWorkflowPlan = (steps: string[]) =>
  apiFetch<{ workflow_plan: string[] }>("/workflow", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ steps }),
  });

export const fetchWorkflowPlan = () =>
  apiFetch<{ workflow_plan: string[] }>("/workflow");

export const fetchGraph = () => apiFetch<GraphBlueprint>("/workflow_graph");

export const saveGraph = (graph: GraphBlueprint) =>
  apiFetch<GraphBlueprint>("/workflow_graph", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(graph),
  });

export const fetchAgentSettings = () =>
  apiFetch<{ agents: AgentSettingsMap }>("/agent_settings");

export const saveAgentSettings = (agents: AgentSettingsMap) =>
  apiFetch<{ agents: AgentSettingsMap }>("/agent_settings", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ agents }),
  });

export const fetchTraces = (limit = 5) =>
  apiFetch<{ traces: TraceSummary[] }>(`/traces?limit=${limit}`);
