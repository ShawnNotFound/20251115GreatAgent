import type { AgentDefinition } from "../types";

export const AGENT_LIBRARY: AgentDefinition[] = [
  {
    id: "InputAgent",
    label: "Input",
    description: "Take input, decide task difficulty, decide whether to use multi-agents.",
    type: "stem",
    implemented: true,
  },
  {
    id: "TaskDecomposer",
    label: "Task Decomposer",
    description: "Break a query into a workflow, choose tools, and emit Langflow-ready JSON.",
    type: "stem",
    implemented: true,
  },
  {
    id: "OutputAgent",
    label: "Output",
    description: "Organize results and craft final wording.",
    type: "stem",
    implemented: true,
  },
  {
    id: "ResearchAgent",
    label: "Research",
    description: "Surf the web, gather robust knowledge, return structured candidates.",
    type: "tool",
    implemented: true,
  },
  {
    id: "ValidationAgent",
    label: "Validation",
    description: "Critical web-backed fact checking with notes.",
    type: "tool",
    implemented: true,
  },
  {
    id: "AnalysisAgent",
    label: "Analysis",
    description: "Large-context reasoning, can run Python in a VM.",
    type: "tool",
    implemented: true,
  },
  {
    id: "LogicAgent",
    label: "Logic",
    description: "Deep thinking SOTA solver for any problem.",
    type: "tool",
    implemented: false,
  },
  {
    id: "GithubAgent",
    label: "GitHub",
    description: "Access repositories, craft PRs, trigger actions.",
    type: "addon",
    implemented: false,
  },
  {
    id: "ZoomAgent",
    label: "Zoom",
    description: "Create and schedule Zoom meetings.",
    type: "addon",
    implemented: false,
  },
  {
    id: "CalendarAgent",
    label: "Calendar",
    description: "Manage subscription calendars, sync availability.",
    type: "addon",
    implemented: false,
  },
  {
    id: "KnowledgeTable",
    label: "Knowledge Table",
    description: "Shared data table operators can reference during runs.",
    type: "database",
    implemented: false,
  },
];

export const DEFAULT_PIPELINE = [
  "ResearchAgent",
  "AnalysisAgent",
  "ValidationAgent",
  "OutputAgent",
] as const;

export const STEM_AGENT_IDS = AGENT_LIBRARY.filter((agent) => agent.type === "stem").map(
  (agent) => agent.id,
);

export const IMPLEMENTED_AGENT_IDS = AGENT_LIBRARY.filter(
  (agent) => agent.implemented,
).map((agent) => agent.id);

export const AGENT_LOOKUP = Object.fromEntries(
  AGENT_LIBRARY.map((agent) => [agent.id, agent]),
);
