import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
} from "reactflow";
import type { Connection, Edge, EdgeChange, Node, NodeChange } from "reactflow";

import "./App.css";

import { API_BASE, ENVIRONMENT_NAME } from "./config";
import { AGENT_LIBRARY, AGENT_LOOKUP, DEFAULT_PIPELINE } from "./data/agents";
import {
  fetchAgentSettings,
  fetchGraph,
  fetchTraces,
  fetchWorkflowPlan,
  pauseRun,
  resumeRun,
  saveAgentSettings,
  saveGraph,
  saveWorkflowPlan,
  startRun,
  stopRun,
  submitSelection,
} from "./lib/api";
import type {
  AgentConfig,
  AgentErrorPayload,
  AgentSettingsMap,
  GraphEdge,
  GraphNode,
  TraceSummary,
  RunTraceMeta,
  NodeStatus,
  NodeStatusMap,
  RunMode,
  SegmentRecord,
  WorkflowSnapshot,
} from "./types";

type AgentNodeData = GraphNode & { status: NodeStatus };

interface EventLine {
  ts: number;
  event: string;
  detail: string;
}

interface ControlPanelProps {
  environment: string;
  userQuery: string;
  mode: RunMode;
  status: string;
  activeRunId: string | null;
  lastRunId: string | null;
  canStart: boolean;
  isStarting: boolean;
  settingsReady: boolean;
  missingAgents: string[];
  agentError: AgentErrorPayload | null;
  traceMeta: RunTraceMeta | null;
  errorDetails: string | null;
  onUserQueryChange: (value: string) => void;
  onModeChange: (mode: RunMode) => void;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
}

interface PipelineBuilderProps {
  plan: string[];
  onPlanChange: (plan: string[]) => void;
  onSave: () => Promise<void> | void;
  saving: boolean;
  lastSavedAt: number | null;
}

interface WorkflowCanvasProps {
  nodes: Node<AgentNodeData>[];
  edges: Edge[];
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  onSelectionChange: (nodeId: string | null) => void;
  onSaveLayout: () => Promise<void> | void;
  saving: boolean;
}

interface SegmentInspectorProps {
  nodeId: string | null;
  segments: Record<string, SegmentRecord>;
}

interface EventLogProps {
  events: EventLine[];
}

interface SelectionPanelProps {
  pending: Record<string, string[]>;
  drafts: Record<string, number>;
  onDraftChange: (node: string, value: number) => void;
  onSubmit: (node: string, choiceIndex: number) => void;
  disabled: boolean;
}

interface TimelineProps {
  snapshot: WorkflowSnapshot | null;
}

interface TracePanelProps {
  traceMeta: RunTraceMeta | null;
  traces: TraceSummary[];
}

interface SettingsPanelProps {
  settings: AgentSettingsMap;
  loaded: boolean;
  saving: boolean;
  statusMessage: string | null;
  onFieldChange: (agentId: string, field: keyof AgentConfig, value: string) => void;
  onSave: () => void;
}

const implementedPipelineAgents = AGENT_LIBRARY.filter(
  (agent) =>
    agent.implemented &&
    !["InputAgent", "TaskDecomposer", "WorkflowOrchestrator"].includes(agent.id),
);

const defaultQuery = "Compare Llama-3.1 and GPT-4o for doc summarization.";
const REQUIRED_AGENT_FIELDS: Array<keyof AgentConfig> = ["api_base", "api_key"];

function App() {
  const [userQuery, setUserQuery] = useState(defaultQuery);
  const [mode, setMode] = useState<RunMode>("auto");
  const [workflowPlan, setWorkflowPlan] = useState<string[]>(() => [...DEFAULT_PIPELINE]);
  const [planSaving, setPlanSaving] = useState(false);
  const [planSavedAt, setPlanSavedAt] = useState<number | null>(null);
  const [flowNodes, setFlowNodes] = useState<Node<AgentNodeData>[]>([]);
  const [flowEdges, setFlowEdges] = useState<Edge[]>([]);
  const [graphSaving, setGraphSaving] = useState(false);
  const [graphLoaded, setGraphLoaded] = useState(false);
  const [segments, setSegments] = useState<Record<string, SegmentRecord>>({});
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [eventLines, setEventLines] = useState<EventLine[]>([]);
  const [pendingOptions, setPendingOptions] = useState<Record<string, string[]>>({});
  const [selectionDrafts, setSelectionDrafts] = useState<Record<string, number>>({});
  const [nodeStatuses, setNodeStatuses] = useState<NodeStatusMap>({});
  const [runId, setRunId] = useState<string | null>(null);
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState("idle");
  const [startingRun, setStartingRun] = useState(false);
  const [workflowSnapshot, setWorkflowSnapshot] = useState<WorkflowSnapshot | null>(null);
  const [agentSettings, setAgentSettings] = useState<AgentSettingsMap>({});
  const [traceMeta, setTraceMeta] = useState<RunTraceMeta | null>(null);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  const [agentError, setAgentError] = useState<AgentErrorPayload | null>(null);
  const [errorDetails, setErrorDetails] = useState<string | null>(null);

  const streamRef = useRef<EventSource | null>(null);

  useEffect(() => {
    fetchWorkflowPlan()
      .then((res) => {
        if (Array.isArray(res.workflow_plan) && res.workflow_plan.length) {
          setWorkflowPlan(res.workflow_plan);
          setPlanSavedAt(Date.now());
        }
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    fetchAgentSettings()
      .then((res) => {
        if (res.agents) {
          setAgentSettings(res.agents);
        }
      })
      .catch(() => null)
      .finally(() => setSettingsLoaded(true));
  }, []);


  useEffect(() => {
    fetchTraces()
      .then((res) => setTraces(res.traces || []))
      .catch(() => setTraces([]));
  }, [runStatus]);
  useEffect(() => {
    fetchGraph()
      .then((graph) => {
        hydrateGraph(graph.nodes, graph.edges);
        setGraphLoaded(true);
      })
      .catch(() => {
        hydrateGraph([], []);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hydrateGraph = useCallback(
    (nodes: GraphNode[], edges: GraphEdge[]) => {
      setFlowNodes(
        nodes.length
          ? nodes.map((node, idx) => toFlowNode(node, idx, nodeStatuses[node.id]))
          : defaultNodes(nodeStatuses),
      );
      setFlowEdges(
        edges.length
          ? edges.map((edge, idx) => ({
              id: `${edge.source}-${edge.target}-${idx}`,
              source: edge.source,
              target: edge.target,
              label: edge.label,
              markerEnd: {
                type: MarkerType.ArrowClosed,
              },
            }))
          : defaultEdges(),
      );
    },
    [nodeStatuses],
  );

  useEffect(() => {
    setFlowNodes((nodes) =>
      nodes.map((node) => ({
        ...node,
        data: { ...node.data, status: nodeStatuses[node.id] ?? "idle" },
        className: buildNodeClass(node.data as AgentNodeData, nodeStatuses[node.id] ?? "idle"),
      })),
    );
  }, [nodeStatuses]);

  useEffect(() => {
    if (!settingsMessage) return;
    const timer = setTimeout(() => setSettingsMessage(null), 4000);
    return () => clearTimeout(timer);
  }, [settingsMessage]);

  const appendEvent = useCallback((event: string, payload: unknown) => {
    setEventLines((lines) => {
      const detail =
        typeof payload === "string"
          ? payload
          : JSON.stringify(payload, null, 2);
      const next = [...lines, { ts: Date.now(), event, detail }];
      if (next.length > 160) {
        next.shift();
      }
      return next;
    });
  }, []);

  useEffect(() => {
    if (!runId) {
      streamRef.current?.close();
      streamRef.current = null;
      return;
    }

    const streamUrl = new URL(`/events/${runId}`, API_BASE).toString();
    const source = new EventSource(streamUrl);

    streamRef.current = source;
    setRunStatus("running");

    const parsePayload = (raw: string) => {
      try {
        return JSON.parse(raw);
      } catch {
        return raw;
      }
    };

    const register = (eventName: string, handler?: (payload: any) => void) => {
      source.addEventListener(eventName, (evt) => {
        const payload = parsePayload((evt as MessageEvent).data);
        appendEvent(eventName, payload);
        handler?.(payload);
      });
    };

    register("trace", (payload: RunTraceMeta) => {
      setTraceMeta(payload);
      fetchTraces().then((res) => setTraces(res.traces || [])).catch(() => null);
    });

    register("workflow", (payload: WorkflowSnapshot) => {
      setWorkflowSnapshot(payload);
      if (!graphLoaded && payload.graph) {
        hydrateGraph(payload.graph.nodes, payload.graph.edges);
        setGraphLoaded(true);
      }
      if (payload.steps?.length) {
        setNodeStatuses((prev) => {
          const next = { ...prev };
          payload.steps.forEach((step) => {
            next[step.agent] = normalizeStatus(step.status);
          });
          return next;
        });
      }
    });

    register("segment", (payload: { node: string; input: any; output: any }) => {
      setSegments((prev) => ({
        ...prev,
        [payload.node]: { input: payload.input ?? {}, output: payload.output ?? {} },
      }));
      setNodeStatuses((prev) => ({ ...prev, [payload.node]: "completed" }));
    });

    register("options", (payload: { node: string; options: string[] }) => {
      setPendingOptions((prev) => ({ ...prev, [payload.node]: payload.options || [] }));
      setSelectionDrafts((prev) => ({ ...prev, [payload.node]: 0 }));
    });

    register("awaiting_selection", (payload: { node: string }) => {
      setNodeStatuses((prev) => ({ ...prev, [payload.node]: "awaiting" }));
    });

    register("selection", (payload: { node: string }) => {
      setPendingOptions((prev) => {
        const clone = { ...prev };
        delete clone[payload.node];
        return clone;
      });
      setSelectionDrafts((prev) => {
        const clone = { ...prev };
        delete clone[payload.node];
        return clone;
      });
    });

    register("enter", (payload: { node: string }) => {
      setNodeStatuses((prev) => ({ ...prev, [payload.node]: "active" }));
    });

    register("exit", (payload: { node: string }) => {
      setNodeStatuses((prev) => ({ ...prev, [payload.node]: "completed" }));
    });

    register("paused", () => setRunStatus("paused"));
    register("agent_error", (payload: AgentErrorPayload) => {
      setRunStatus("paused_error");
      setAgentError(payload);
      setErrorDetails(payload?.message || "Agent error");
    });
    register("resumed", () => {
      setRunStatus("running");
      setAgentError(null);
      setErrorDetails(null);
    });
    register("stopping", () => setRunStatus("stopping"));
    register("done", (payload) => {
      appendEvent("final", payload);
      setRunStatus("done");
      setRunId(null);
      setAgentError(null);
      setErrorDetails(null);
    });
    register("error", (payload: { message?: string }) => {
      setRunStatus("error");
      setRunId(null);
      setErrorDetails(payload?.message || "Unknown error");
    });
    register("end", () => {
      source.close();
      streamRef.current = null;
    });

    source.onerror = (evt) => {
      const errType = (evt as Event).type;
      appendEvent("stream_error", errType);
      setRunStatus("error");
      setErrorDetails(`Stream error: ${errType}`);
    };

    return () => {
      source.close();
      streamRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, appendEvent, graphLoaded, hydrateGraph]);

  const resetRunContext = () => {
    setSegments({});
    setPendingOptions({});
    setSelectionDrafts({});
    setNodeStatuses({});
    setWorkflowSnapshot(null);
    setEventLines([]);
    setSelectedNodeId(null);
    setAgentError(null);
    setErrorDetails(null);
    setTraceMeta(null);
  };

  const handleStart = async () => {
    if (!userQuery.trim()) return;
    setStartingRun(true);
    resetRunContext();
    try {
      const payload = await startRun(userQuery.trim(), mode, workflowPlan);
      setRunId(payload.run_id);
      setLastRunId(payload.run_id);
    } catch (err) {
      const message = (err as Error).message;
      appendEvent("start_error", message);
      setRunStatus("error");
      setSettingsMessage(message);
      setErrorDetails(message);
    } finally {
      setStartingRun(false);
    }
  };

  const handlePause = async () => {
    if (!runId) return;
    await pauseRun(runId);
  };

  const handleResume = async () => {
    if (!runId) return;
    await resumeRun(runId);
  };

  const handleStop = async () => {
    if (!runId) return;
    await stopRun(runId);
  };

  const handleSavePlan = async () => {
    setPlanSaving(true);
    try {
      await saveWorkflowPlan(workflowPlan);
      setPlanSavedAt(Date.now());
    } finally {
      setPlanSaving(false);
    }
  };

  const handleSaveGraph = async () => {
    setGraphSaving(true);
    try {
      await saveGraph({
        nodes: flowNodes.map((node, idx) => toGraphNode(node, idx)),
        edges: flowEdges.map((edge) => toGraphEdge(edge)),
      });
    } finally {
      setGraphSaving(false);
    }
  };

  const handleSelectionSubmit = async (node: string, choiceIndex: number) => {
    const targetRunId = runId ?? lastRunId;
    if (!targetRunId) return;
    await submitSelection(targetRunId, node, choiceIndex);
    setSelectionDrafts((prev) => ({ ...prev, [node]: choiceIndex }));
  };

  const handleAgentSettingChange = (agentId: string, field: keyof AgentConfig, value: string) => {
    setAgentSettings((prev) => {
      const current = prev[agentId] ?? { api_base: "", api_key: "", model: "", prompt: "" };
      return {
        ...prev,
        [agentId]: {
          ...current,
          [field]: value,
        },
      };
    });
  };

  const handleAgentSettingsSave = async () => {
    setSettingsSaving(true);
    try {
      const result = await saveAgentSettings(agentSettings);
      if (result.agents) {
        setAgentSettings(result.agents);
      }
      setSettingsMessage("Agent settings saved");
    } catch (err) {
      setSettingsMessage(`Save failed: ${(err as Error).message}`);
    } finally {
      setSettingsSaving(false);
    }
  };

  const onNodesChange = useCallback(
    (changes: NodeChange[]) =>
      setFlowNodes((nds) => applyNodeChanges(changes, nds)),
    [],
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) =>
      setFlowEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  );

  const onConnect = useCallback(
    (connection: Connection) =>
      setFlowEdges((eds) =>
        addEdge(
          {
            ...connection,
            type: "smoothstep",
            markerEnd: { type: MarkerType.ArrowClosed },
          },
          eds,
        ),
      ),
    [],
  );

  const missingAgentSettings = useMemo(() => {
    if (!settingsLoaded) return null;
    return Object.entries(agentSettings).filter(([, config]) =>
      REQUIRED_AGENT_FIELDS.some((field) => !(config?.[field]?.trim())),
    );
  }, [agentSettings, settingsLoaded]);

  const settingsReady = Boolean(missingAgentSettings && missingAgentSettings.length === 0);

  const missingAgentIds = missingAgentSettings?.map(([agent]) => agent) ?? [];

  const nodeSegments = useMemo(() => segments, [segments]);

  const selectionDisabled = mode !== "human" || (!runId && !lastRunId);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>GreatAgent Orchestrator</h1>
          <p>Visual multi-agent Langflow runs with human-in-the-loop controls.</p>
        </div>
        <div className="header-meta">
          <span className="env-pill">{ENVIRONMENT_NAME}</span>
          <span className={`run-status status-${runStatus}`}>{runStatus}</span>
          {lastRunId && (
            <span className="run-id">Last run: {lastRunId.slice(0, 8)}</span>
          )}
        </div>
      </header>

      <main className="app-grid">
        <div className="column">
          <ControlPanel
            environment={ENVIRONMENT_NAME}
            userQuery={userQuery}
            mode={mode}
            status={runStatus}
            activeRunId={runId}
            lastRunId={lastRunId}
            canStart={Boolean(userQuery.trim())}
            isStarting={startingRun}
            settingsReady={settingsReady}
            missingAgents={missingAgentIds}
            agentError={agentError}
            traceMeta={traceMeta}
            errorDetails={errorDetails}
            onUserQueryChange={setUserQuery}
            onModeChange={setMode}
            onStart={handleStart}
            onPause={handlePause}
            onResume={handleResume}
            onStop={handleStop}
          />

          <PipelineBuilder
            plan={workflowPlan}
            onPlanChange={setWorkflowPlan}
            onSave={handleSavePlan}
            saving={planSaving}
            lastSavedAt={planSavedAt}
          />

          <Timeline snapshot={workflowSnapshot} />
        </div>

        <div className="column">
          <WorkflowCanvas
            nodes={flowNodes}
            edges={flowEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onSelectionChange={setSelectedNodeId}
            onSaveLayout={handleSaveGraph}
            saving={graphSaving}
          />

          <EventLog events={eventLines} />
        </div>

        <div className="column">
          <SegmentInspector nodeId={selectedNodeId} segments={nodeSegments} />
          <SelectionPanel
            pending={pendingOptions}
            drafts={selectionDrafts}
            disabled={selectionDisabled}
            onDraftChange={(node, value) =>
              setSelectionDrafts((prev) => ({ ...prev, [node]: value }))
            }
            onSubmit={handleSelectionSubmit}
          />
          <TracePanel traceMeta={traceMeta} traces={traces} />
          <SettingsPanel
            settings={agentSettings}
            loaded={settingsLoaded}
            saving={settingsSaving}
            statusMessage={settingsMessage}
            onFieldChange={handleAgentSettingChange}
            onSave={handleAgentSettingsSave}
          />
        </div>
      </main>
    </div>
  );
}

const ControlPanel = ({
  environment,
  userQuery,
  mode,
  status,
  activeRunId,
  lastRunId,
  canStart,
  isStarting,
  settingsReady,
  missingAgents,
  agentError,
  traceMeta,
  errorDetails,
  onUserQueryChange,
  onModeChange,
  onStart,
  onPause,
  onResume,
  onStop,
}: ControlPanelProps) => (
  <section className="panel">
    <header className="panel-header">
      <div>
        <h2>Run Control</h2>
        <p className="panel-subtitle">Environment: {environment}</p>
      </div>
      <span className={`run-status status-${status}`}>{status}</span>
    </header>
    <label className="field">
      <span>User query</span>
      <textarea
        value={userQuery}
        onChange={(evt) => onUserQueryChange(evt.target.value)}
        rows={3}
      />
    </label>
    <label className="field">
      <span>Mode</span>
      <select value={mode} onChange={(evt) => onModeChange(evt.target.value as RunMode)}>
        <option value="auto">Agents only</option>
        <option value="human">Engage human</option>
      </select>
    </label>
    <div className="button-row">
      <button
        onClick={onStart}
        disabled={!canStart || isStarting || Boolean(activeRunId)}
      >
        {isStarting ? "Starting..." : "Start"}
      </button>
      <button onClick={onPause} disabled={!activeRunId}>
        Pause
      </button>
      <button onClick={onResume} disabled={!activeRunId}>
        Resume
      </button>
      <button onClick={onStop} disabled={!activeRunId}>
        Stop
      </button>
    </div>
    {!settingsReady && missingAgents.length > 0 && (
      <p className="hint error">
        Provide API base + key for: {missingAgents.join(", ")}
      </p>
    )}
    {agentError && (
      <p className="hint error">
        Paused on {agentError.node}: {agentError.message}
      </p>
    )}

    {errorDetails && (
      <p className="hint error">
        Error details: {errorDetails}
      </p>
    )}

    {traceMeta && (
      <p className="hint">
        Trace: <a href={traceMeta.trace_url} target="_blank" rel="noreferrer">{traceMeta.trace_id}</a>
      </p>
    )}
    {lastRunId && !activeRunId && (
      <p className="hint">Most recent run id: {lastRunId}</p>
    )}
  </section>
);

const PipelineBuilder = ({ plan, onPlanChange, onSave, saving, lastSavedAt }: PipelineBuilderProps) => {
  const move = (index: number, delta: number) => {
    const nextIndex = index + delta;
    if (nextIndex < 0 || nextIndex >= plan.length) return;
    const clone = [...plan];
    const [item] = clone.splice(index, 1);
    clone.splice(nextIndex, 0, item);
    onPlanChange(clone);
  };

  const remove = (index: number) => {
    const clone = plan.filter((_, idx) => idx !== index);
    onPlanChange(clone);
  };

  const add = (id: string) => {
    onPlanChange([...plan, id]);
  };

  const reset = () => onPlanChange([...DEFAULT_PIPELINE]);

  const nextCandidates = implementedPipelineAgents.filter((agent) => !plan.includes(agent.id));

  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h2>Pipeline Builder</h2>
          <p className="panel-subtitle">Focus on stem agents first, then mix in tools.</p>
        </div>
        <button onClick={() => onSave()} disabled={saving}>
          {saving ? "Saving..." : "Save plan"}
        </button>
      </header>
      <ol className="plan-list">
        {plan.map((agentId, idx) => {
          const def = AGENT_LOOKUP[agentId];
          return (
            <li key={`${agentId}-${idx}`}>
              <div>
                <strong>{def?.label ?? agentId}</strong>
                <p>{def?.description}</p>
              </div>
              <div className="plan-actions">
                <button onClick={() => move(idx, -1)} disabled={idx === 0}>
                  ↑
                </button>
                <button onClick={() => move(idx, 1)} disabled={idx === plan.length - 1}>
                  ↓
                </button>
                <button onClick={() => remove(idx)}>×</button>
              </div>
            </li>
          );
        })}
      </ol>
      <div className="plan-add-row">
        <select
          onChange={(evt) => {
            const value = evt.target.value;
            if (value) {
              add(value);
              evt.target.value = "";
            }
          }}
          defaultValue=""
        >
          <option value="" disabled>
            Add agent…
          </option>
          {nextCandidates.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.label}
            </option>
          ))}
        </select>
        <button onClick={reset}>Reset default</button>
      </div>
      {lastSavedAt && (
        <p className="hint">Plan saved {new Date(lastSavedAt).toLocaleTimeString()}</p>
      )}
    </section>
  );
};

const WorkflowCanvas = ({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onSelectionChange,
  onSaveLayout,
  saving,
}: WorkflowCanvasProps) => (
  <section className="panel workflow-panel">
    <header className="panel-header">
      <div>
        <h2>Workflow Canvas</h2>
        <p className="panel-subtitle">Drag nodes, wire edges, then save the Langflow graph.</p>
      </div>
      <button onClick={onSaveLayout} disabled={saving}>
        {saving ? "Saving..." : "Save layout"}
      </button>
    </header>
    <div className="canvas-wrapper">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onSelectionChange={({ nodes }) => onSelectionChange(nodes[0]?.id ?? null)}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} />
        <Controls />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  </section>
);

const SegmentInspector = ({ nodeId, segments }: SegmentInspectorProps) => {
  const segment = nodeId ? segments[nodeId] : null;
  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h2>Segment Inspector</h2>
          <p className="panel-subtitle">Tap a node to inspect inputs/outputs.</p>
        </div>
        {nodeId && <span className="tag">{nodeId}</span>}
      </header>
      {segment ? (
        <>
          <strong>Inputs</strong>
          <pre>{JSON.stringify(segment.input, null, 2)}</pre>
          <strong>Outputs</strong>
          <pre>{JSON.stringify(segment.output, null, 2)}</pre>
        </>
      ) : (
        <p className="hint">Select a node to see its trace.</p>
      )}
    </section>
  );
};

const EventLog = ({ events }: EventLogProps) => (
  <section className="panel">
    <header className="panel-header">
      <div>
        <h2>Event Log</h2>
        <p className="panel-subtitle">Latest server-sent events.</p>
      </div>
    </header>
    <div className="event-log">
      {events.slice(-12).map((event) => (
        <div key={event.ts + event.event}>
          <strong>{event.event}</strong>
          <pre>{event.detail}</pre>
        </div>
      ))}
      {!events.length && <p className="hint">Start a run to stream events.</p>}
    </div>
  </section>
);


const TracePanel = ({ traceMeta, traces }: TracePanelProps) => (
  <section className="panel">
    <header className="panel-header">
      <div>
        <h2>LangSmith Traces</h2>
        <p className="panel-subtitle">Latest runs pushed to LangSmith.</p>
      </div>
    </header>
    {traceMeta && (
      <p className="hint">Current run: <a href={traceMeta.trace_url} target="_blank" rel="noreferrer">{traceMeta.trace_id}</a></p>
    )}
    <ul className="trace-list">
      {traces.map((trace) => (
        <li key={trace.id}>
          <strong>{trace.name || trace.id}</strong> — {trace.status}
          {trace.url && (
            <a href={trace.url} target="_blank" rel="noreferrer" className="trace-link">View</a>
          )}
        </li>
      ))}
      {!traces.length && <li className="hint">No trace data yet.</li>}
    </ul>
  </section>
);

const SelectionPanel = ({ pending, drafts, onDraftChange, onSubmit, disabled }: SelectionPanelProps) => {
  const entries = Object.entries(pending);
  if (!entries.length) {
    return (
      <section className="panel">
        <header className="panel-header">
          <div>
            <h2>Human Selections</h2>
            <p className="panel-subtitle">Idle until a human checkpoint fires.</p>
          </div>
        </header>
        <p className="hint">No pending selections.</p>
      </section>
    );
  }
  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h2>Human Selections</h2>
          <p className="panel-subtitle">Pick an option per node to continue.</p>
        </div>
      </header>
      {entries.map(([node, options]) => (
        <div key={node} className="selection-block">
          <strong>{node}</strong>
          {options.map((option, idx) => (
            <label key={idx} className="option-row">
              <input
                type="radio"
                name={`sel-${node}`}
                value={idx}
                checked={(drafts[node] ?? 0) === idx}
                onChange={() => onDraftChange(node, idx)}
                disabled={disabled}
              />
              <span>{option}</span>
            </label>
          ))}
          <button
            onClick={() => onSubmit(node, drafts[node] ?? 0)}
            disabled={disabled}
          >
            Confirm
          </button>
        </div>
      ))}
    </section>
  );
};

const SETTINGS_FIELDS: Array<{ key: keyof AgentConfig; label: string; type?: "textarea" }> = [
  { key: "api_base", label: "API Base URL" },
  { key: "api_key", label: "API Key" },
  { key: "model", label: "Model" },
  { key: "prompt", label: "Prompt", type: "textarea" },
];

const SettingsPanel = ({
  settings,
  loaded,
  saving,
  statusMessage,
  onFieldChange,
  onSave,
}: SettingsPanelProps) => {
  const entries = Object.entries(settings || {}).sort((a, b) => a[0].localeCompare(b[0]));

  return (
    <section className="panel settings-panel">
      <header className="panel-header">
        <div>
          <h2>Agent Settings</h2>
          <p className="panel-subtitle">API endpoints, keys, models, and prompts per agent.</p>
        </div>
        <button onClick={onSave} disabled={saving || !loaded}>
          {saving ? "Saving..." : "Save settings"}
        </button>
      </header>
      {!loaded ? (
        <p className="hint">Loading settings…</p>
      ) : !entries.length ? (
        <p className="hint">No agents registered yet.</p>
      ) : (
        <div className="agent-settings-grid">
          {entries.map(([agentId, config]) => (
            <details key={agentId} open className="agent-setting-card">
              <summary>
                <strong>{agentId}</strong>
              </summary>
              <div className="settings-fields">
                {SETTINGS_FIELDS.map((field) => (
                  <label key={field.key} className="field">
                    <span>{field.label}</span>
                    {field.type === "textarea" ? (
                      <textarea
                        rows={4}
                        value={config?.[field.key] ?? ""}
                        onChange={(evt) => onFieldChange(agentId, field.key, evt.target.value)}
                      />
                    ) : (
                      <input
                        type="text"
                        value={config?.[field.key] ?? ""}
                        onChange={(evt) => onFieldChange(agentId, field.key, evt.target.value)}
                      />
                    )}
                  </label>
                ))}
              </div>
            </details>
          ))}
        </div>
      )}
      {statusMessage && <p className="hint">{statusMessage}</p>}
    </section>
  );
};

const Timeline = ({ snapshot }: TimelineProps) => {
  if (!snapshot?.steps?.length) {
    return (
      <section className="panel">
        <header className="panel-header">
          <div>
            <h2>Timeline</h2>
            <p className="panel-subtitle">Workflow progress appears here.</p>
          </div>
        </header>
        <p className="hint">Start a run to populate the timeline.</p>
      </section>
    );
  }
  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h2>Timeline</h2>
          <p className="panel-subtitle">Mode: {snapshot.mode}</p>
        </div>
      </header>
      <ul className="timeline">
        {snapshot.steps.map((step) => (
          <li key={step.agent}>
            <strong>{step.agent}</strong>
            <span className={`status-chip status-${normalizeStatus(step.status)}`}>
              {step.status}
            </span>
            {step.requires_human && <span className="tag">human</span>}
            <p>{step.notes}</p>
          </li>
        ))}
      </ul>
    </section>
  );
};

const toFlowNode = (node: GraphNode, idx: number, status?: NodeStatus): Node<AgentNodeData> => ({
  id: node.id,
  position: {
    x: node.x ?? 80 + idx * 220,
    y:
      node.y ??
      (node.type === "stem" ? 40 : node.type === "tool" ? 220 : node.type === "addon" ? 360 : 500),
  },
  data: {
    ...node,
    label: node.label ?? node.id,
    status: status ?? "idle",
  },
  draggable: true,
  className: buildNodeClass(node, status ?? "idle"),
});

const BASE_GRAPH: GraphNode[] = [
  { id: "InputAgent", label: "Input", type: "stem", order: 0, x: 40, y: 40 },
  {
    id: "TaskDecomposer",
    label: "Task Decomposer",
    type: "stem",
    order: 1,
    x: 240,
    y: 40,
  },
  {
    id: "WorkflowOrchestrator",
    label: "Workflow Orchestrator",
    type: "stem",
    order: 2,
    x: 460,
    y: 40,
  },
  {
    id: "ResearchAgent",
    label: "Research",
    type: "tool",
    order: 3,
    x: 680,
    y: 40,
  },
  {
    id: "AnalysisAgent",
    label: "Analysis",
    type: "tool",
    order: 4,
    x: 900,
    y: 40,
  },
  {
    id: "ValidationAgent",
    label: "Validation",
    type: "tool",
    order: 5,
    x: 1120,
    y: 40,
  },
  {
    id: "OutputAgent",
    label: "Output",
    type: "stem",
    order: 6,
    x: 1340,
    y: 40,
  },
];

const BASE_EDGES: GraphEdge[] = [
  { source: "InputAgent", target: "TaskDecomposer" },
  { source: "TaskDecomposer", target: "WorkflowOrchestrator" },
  { source: "WorkflowOrchestrator", target: "ResearchAgent" },
  { source: "ResearchAgent", target: "AnalysisAgent" },
  { source: "AnalysisAgent", target: "ValidationAgent" },
  { source: "ValidationAgent", target: "OutputAgent" },
];

const defaultNodes = (statusMap: NodeStatusMap): Node<AgentNodeData>[] =>
  BASE_GRAPH.map((node, idx) => toFlowNode(node, idx, statusMap[node.id]));

const defaultEdges = (): Edge[] =>
  BASE_EDGES.map((edge, idx) => ({
    id: `${edge.source}-${edge.target}-${idx}`,
    source: edge.source,
    target: edge.target,
    markerEnd: { type: MarkerType.ArrowClosed },
  }));

const toGraphNode = (node: Node<AgentNodeData>, idx: number): GraphNode => ({
  id: node.id,
  label: node.data.label,
  requires_human: Boolean(node.data.requires_human),
  order: node.data.order ?? idx,
  type: node.data.type,
  x: node.position.x,
  y: node.position.y,
});

const toGraphEdge = (edge: Edge): GraphEdge => ({
  source: edge.source,
  target: edge.target,
  label: typeof edge.label === "string" ? edge.label : undefined,
});

const buildNodeClass = (node: GraphNode, status: NodeStatus) =>
  `agent-node type-${node.type ?? "tool"} status-${status}`;

const normalizeStatus = (status: string): NodeStatus => {
  if (!status) return "idle";
  const normalized = status.toLowerCase();
  if (normalized.includes("await")) return "awaiting";
  if (normalized.includes("active")) return "active";
  if (normalized.includes("complete")) return "completed";
  if (normalized.includes("error")) return "error";
  if (normalized.includes("ready")) return "ready";
  return "idle";
};

export default App;
