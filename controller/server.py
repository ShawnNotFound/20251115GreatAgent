from __future__ import annotations
import asyncio
import json
import uuid
import time
from enum import Enum
from copy import deepcopy

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field

from agent_core.pipeline import AgentPipeline
from controller.langsmith_client import fetch_recent_traces
from controller.settings_store import (
    get_agent_settings,
    update_agent_settings,
)

app = FastAPI(title="GreatAgent Controller")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS: dict[str, dict] = {}
EVENT_QUEUES: dict[str, asyncio.Queue] = {}

DEFAULT_GRAPH_BLUEPRINT = {
    "nodes": [
        {"id": "InputAgent", "label": "Input", "type": "stem", "order": 0, "x": 40, "y": 40},
        {"id": "TaskDecomposer", "label": "Task", "type": "stem", "order": 1, "x": 240, "y": 40},
        {"id": "WorkflowOrchestrator", "label": "Workflow", "type": "stem", "order": 2, "x": 460, "y": 40},
        {"id": "ResearchAgent", "label": "Research", "type": "tool", "order": 3, "x": 680, "y": 40},
        {"id": "AnalysisAgent", "label": "Analysis", "type": "tool", "order": 4, "x": 900, "y": 40},
        {"id": "ValidationAgent", "label": "Validation", "type": "tool", "order": 5, "x": 1120, "y": 40},
        {"id": "OutputAgent", "label": "Output", "type": "stem", "order": 6, "x": 1340, "y": 40},
    ],
    "edges": [
        {"source": "InputAgent", "target": "TaskDecomposer"},
        {"source": "TaskDecomposer", "target": "WorkflowOrchestrator"},
        {"source": "WorkflowOrchestrator", "target": "ResearchAgent"},
        {"source": "ResearchAgent", "target": "AnalysisAgent"},
        {"source": "AnalysisAgent", "target": "ValidationAgent"},
        {"source": "ValidationAgent", "target": "OutputAgent"},
    ],
}

GLOBAL_GRAPH_BLUEPRINT = deepcopy(DEFAULT_GRAPH_BLUEPRINT)
GLOBAL_WORKFLOW_OVERRIDE: list[str] | None = None


class RunMode(str, Enum):
    AUTO = "auto"
    HUMAN = "human"


class StartRunReq(BaseModel):
    user_query: str
    mode: RunMode = Field(default=RunMode.AUTO)


class SelectionReq(BaseModel):
    run_id: str
    node: str
    choice_index: int


class WorkflowUpdateReq(BaseModel):
    steps: list[str]


class GraphNode(BaseModel):
    id: str
    label: str | None = None
    requires_human: bool = False
    order: int | None = None
    type: str | None = None
    x: float | None = None
    y: float | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str | None = None


class WorkflowGraphReq(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class AgentConfig(BaseModel):
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    prompt: str = ""


class AgentSettingsReq(BaseModel):
    agents: dict[str, AgentConfig]


def now_ms() -> int:
    return int(time.time() * 1000)


async def emit(run_id: str, event: str, payload: dict):
    queue = EVENT_QUEUES.get(run_id)
    if queue:
        await queue.put({"event": event, "data": payload})


async def _wait_ok(run_id: str):
    while True:
        run = RUNS[run_id]
        if run["stop"]:
            raise RuntimeError("Stopped by user")
        if not run["paused"]:
            return
        await asyncio.sleep(0.1)


@app.post("/run")
async def start_run(req: StartRunReq):
    run_id = str(uuid.uuid4())
    EVENT_QUEUES[run_id] = asyncio.Queue()
    RUNS[run_id] = {
        "id": run_id,
        "mode": req.mode,
        "status": "running",
        "store": {
            "user_query": req.user_query,
            "selections": {},
            "workflow_override": GLOBAL_WORKFLOW_OVERRIDE,
            "graph_blueprint": deepcopy(GLOBAL_GRAPH_BLUEPRINT),
        },
        "paused": False,
        "stop": False,
    }
    asyncio.create_task(_run_pipeline(run_id))
    return {"run_id": run_id}


@app.get("/events/{run_id}")
async def events(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, "run not found")

    async def gen():
        queue = EVENT_QUEUES.get(run_id)
        while RUNS.get(run_id):
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield {"event": item["event"], "data": json.dumps(item["data"], ensure_ascii=False)}
                if item["event"] in {"done", "error", "stopping"}:
                    break
            except asyncio.TimeoutError:
                run = RUNS[run_id]
                if run["status"] in {"done", "error", "stopping"} and queue.empty():
                    break
        yield {"event": "end", "data": json.dumps({"run_id": run_id})}

    return EventSourceResponse(gen())


@app.post("/pause/{run_id}")
async def pause(run_id: str):
    RUNS[run_id]["paused"] = True
    RUNS[run_id]["status"] = "paused"
    await emit(run_id, "paused", {"ts": now_ms()})
    return {"ok": True}


@app.post("/resume/{run_id}")
async def resume(run_id: str):
    RUNS[run_id]["paused"] = False
    RUNS[run_id]["status"] = "running"
    await emit(run_id, "resumed", {"ts": now_ms()})
    return {"ok": True}


@app.post("/stop/{run_id}")
async def stop(run_id: str):
    RUNS[run_id]["stop"] = True
    RUNS[run_id]["status"] = "stopping"
    await emit(run_id, "stopping", {"ts": now_ms()})
    return {"ok": True}


@app.post("/select")
async def select(req: SelectionReq):
    run = RUNS.get(req.run_id)
    if not run:
        raise HTTPException(404, "run not found")
    run["store"]["selections"][req.node] = req.choice_index
    if run["status"] == "awaiting_selection":
        run["status"] = "running"
    await emit(req.run_id, "selection", {"node": req.node, "choice_index": req.choice_index, "ts": now_ms()})
    return {"ok": True}


@app.post("/workflow")
async def update_workflow(req: WorkflowUpdateReq):
    steps = [step for step in req.steps if step]
    if not steps:
        raise HTTPException(400, "steps cannot be empty")
    global GLOBAL_WORKFLOW_OVERRIDE
    GLOBAL_WORKFLOW_OVERRIDE = steps
    return {"workflow_plan": steps}


@app.get("/workflow")
async def get_workflow():
    return {"workflow_plan": GLOBAL_WORKFLOW_OVERRIDE or []}


@app.get("/workflow_graph")
async def get_workflow_graph():
    return GLOBAL_GRAPH_BLUEPRINT


@app.post("/workflow_graph")
async def set_workflow_graph(req: WorkflowGraphReq):
    global GLOBAL_GRAPH_BLUEPRINT
    GLOBAL_GRAPH_BLUEPRINT = {
        "nodes": [node.model_dump() for node in req.nodes],
        "edges": [edge.model_dump() for edge in req.edges],
    }
    return GLOBAL_GRAPH_BLUEPRINT


@app.get("/agent_settings")
async def get_agent_settings_route():
    return {"agents": get_agent_settings()}


@app.post("/agent_settings")
async def set_agent_settings(req: AgentSettingsReq):
    updated = update_agent_settings({agent: data.model_dump() for agent, data in req.agents.items()})
    return {"agents": updated}


@app.get("/traces")
async def get_traces(limit: int = 5):
    return {"traces": fetch_recent_traces(limit)}


async def _record(run_id: str, node: str, inputs: dict, outputs: dict):
    RUNS[run_id]["store"].setdefault("segments", {})[node] = {"input": inputs, "output": outputs}
    await emit(run_id, "segment", {"node": node, "input": inputs, "output": outputs})


async def _pause_with_error(run_id: str, node: str, message: str):
    run = RUNS[run_id]
    run["paused"] = True
    run["status"] = "paused_error"
    await emit(run_id, "agent_error", {"node": node, "message": message, "ts": now_ms()})


async def _await_selection(run_id: str, node: str, options: list[str], mode_label: str) -> int:
    run = RUNS[run_id]
    choice_idx = 0
    if mode_label == "engage_human" and options:
        run["status"] = "awaiting_selection"
        await emit(run_id, "awaiting_selection", {"node": node})
        while run["status"] == "awaiting_selection":
            await asyncio.sleep(0.1)
        choice_idx = run["store"]["selections"].get(node, 0)
        run["status"] = "running"
    return choice_idx


async def _run_pipeline(run_id: str):
    pipeline = AgentPipeline()
    run = RUNS[run_id]
    mode_label = "engage_human" if run["mode"] == RunMode.HUMAN else "agents_only"

    trace_meta = pipeline.start_trace()
    run["store"]["trace"] = trace_meta
    await emit(run_id, "trace", trace_meta)

    try:
        await _wait_ok(run_id)
        await emit(run_id, "enter", {"node": "InputAgent"})
        intake = pipeline.run_input(run["store"]["user_query"], mode_label, None)
        await emit(run_id, "exit", {"node": "InputAgent", "output": intake})
        await _record(run_id, "InputAgent", {"user_query": run["store"]["user_query"]}, intake)

        await _wait_ok(run_id)
        await emit(run_id, "enter", {"node": "TaskDecomposer"})
        plan = pipeline.run_decomposer(intake["normalized_query"], intake["tools_needed"], intake["constraints"])
        override_plan = run["store"].get("workflow_override")
        if override_plan:
            plan["workflow_plan"] = override_plan
        await emit(run_id, "exit", {"node": "TaskDecomposer", "output": plan})
        await _record(run_id, "TaskDecomposer", {"query": intake["normalized_query"]}, plan)

        await _wait_ok(run_id)
        await emit(run_id, "enter", {"node": "WorkflowOrchestrator"})
        workflow = pipeline.run_workflow(plan["workflow_plan"], intake["engagement_mode"])
        plan_steps = plan["workflow_plan"]
        workflow["graph"] = run["store"]["graph_blueprint"]
        run["store"]["workflow"] = workflow
        await emit(run_id, "workflow", workflow)
        await _record(run_id, "WorkflowOrchestrator", {"plan": plan["workflow_plan"]}, workflow)

        selected_research = intake["normalized_query"]
        selected_analysis = ""
        validation = {}
        final_text = ""

        for node in plan_steps:
            await _wait_ok(run_id)
            await emit(run_id, "enter", {"node": node})

            try:
                if node == "ResearchAgent":
                    research = pipeline.run_research(intake["normalized_query"])
                    options = research["candidates"]
                    await emit(run_id, "options", {"node": node, "options": options})
                    choice_idx = await _await_selection(run_id, node, options, mode_label)
                    selected_research = options[choice_idx] if options else ""
                    await _record(run_id, node, {"query": intake["normalized_query"]}, research)
                elif node == "AnalysisAgent":
                    analysis = pipeline.run_analysis([selected_research])
                    options = analysis["options"]
                    await emit(run_id, "options", {"node": node, "options": options})
                    choice_idx = await _await_selection(run_id, node, options, mode_label)
                    selected_analysis = options[choice_idx] if options else ""
                    await _record(run_id, node, {"selected_input": selected_research}, analysis)
                elif node == "ValidationAgent":
                    validation = pipeline.run_validation(selected_analysis)
                    await _record(run_id, node, {"draft": selected_analysis}, validation)
                elif node == "OutputAgent":
                    final = pipeline.run_output(selected_analysis, validation)
                    final_text = final["final_text"]
                    await _record(run_id, node, {"analysis_choice": selected_analysis, "validation": validation}, final)
            except Exception as exc:
                await _pause_with_error(run_id, node, str(exc))
                return

            await emit(run_id, "exit", {"node": node})

        run["status"] = "done"
        await emit(run_id, "done", {"final": final_text, "trace": trace_meta})
    except Exception as exc:
        run["status"] = "error"
        await emit(run_id, "error", {"message": str(exc)})
