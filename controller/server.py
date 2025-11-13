import asyncio, json, uuid, time
from enum import Enum
from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field

from langflow_components.input_agent import InputAgent
from langflow_components.task_decomposer import TaskDecomposer
from langflow_components.workflow_orchestrator import WorkflowOrchestrator
from langflow_components.research_agent import ResearchAgent
from langflow_components.human_selection_gate import HumanSelectionGate
from langflow_components.analysis_agent import AnalysisAgent
from langflow_components.validation_agent import ValidationAgent
from langflow_components.output_agent import OutputAgent

app = FastAPI(title="AgentGlassFlow Controller")

# --- In-memory run state (OK for hackathon)
RUNS: dict[str, dict] = {}
EVENT_QUEUES: dict[str, asyncio.Queue] = {}

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

def now_ms(): return int(time.time() * 1000)

async def emit(run_id: str, event: str, payload: dict):
    q = EVENT_QUEUES.get(run_id)
    if q:
        await q.put({"event": event, "data": payload})

@app.post("/run")
async def start_run(req: StartRunReq):
    run_id = str(uuid.uuid4())
    EVENT_QUEUES[run_id] = asyncio.Queue()
    RUNS[run_id] = {
        "id": run_id,
        "mode": req.mode,
        "status": "running",
        "cursor": "TaskDecomposer",
        "store": {"user_query": req.user_query, "selections": {}, "segments": {}},
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
                yield {
                    "event": item["event"],
                    "data": json.dumps(item["data"], ensure_ascii=False),
                }
                if item["event"] in {"done", "error", "stopping"}:
                    break
            except asyncio.TimeoutError:
                status = RUNS[run_id]["status"]
                if status in {"done", "error", "stopping"} and queue.empty():
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
    if RUNS[run_id]["status"] == "paused":
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

# --- Demo pipeline runner (mock calls). Replace with Langflow API calls if desired.
async def _run_pipeline(run_id: str):
    run = RUNS[run_id]
    mode_label = "engage_human" if run["mode"] == RunMode.HUMAN else "agents_only"

    async def record(node: str, inputs: dict, output: dict):
        run["store"]["segments"][node] = {"input": inputs, "output": output}
        await emit(run_id, "segment", {"node": node, "input": inputs, "output": output})

    try:
        # Input Agent
        await _wait_ok(run_id)
        await emit(run_id, "enter", {"node": "InputAgent"})
        intake_inputs = {
            "user_query": run["store"]["user_query"],
            "preferred_mode": mode_label,
        }
        intake = InputAgent().build(**intake_inputs)
        await emit(run_id, "exit", {"node": "InputAgent", "output": intake})
        await record("InputAgent", intake_inputs, intake)

        # Task Decomposer
        await _wait_ok(run_id)
        await emit(run_id, "enter", {"node": "TaskDecomposer"})
        plan = TaskDecomposer().build(intake["normalized_query"])
        await emit(run_id, "exit", {"node": "TaskDecomposer", "output": plan})
        await record("TaskDecomposer", {"user_query": intake["normalized_query"]}, plan)

        # Workflow Orchestrator
        await _wait_ok(run_id)
        workflow = WorkflowOrchestrator().build(
            workflow_plan=plan["workflow_plan"],
            engagement_mode=intake["engagement_mode"],
            tools_needed=intake["tools_needed"],
        )
        await emit(run_id, "workflow", workflow)
        await record("WorkflowOrchestrator", {"plan": plan["workflow_plan"]}, workflow)

        # Step through planned agents
        selected_research = intake["normalized_query"]
        selected_analysis = ""
        analysis_options = []
        validation = {}
        final_text = ""
        for node in plan["workflow_plan"]:
            await _wait_ok(run_id)
            await emit(run_id, "enter", {"node": node})

            if node == "ResearchAgent":
                research = ResearchAgent().build(intake["normalized_query"])
                await emit(run_id, "options", {"node": node, "options": research["candidates"]})
                choice_idx = 0
                if mode_label == "engage_human":
                    run["status"] = "awaiting_selection"
                    await emit(run_id, "awaiting_selection", {"node": node})
                    while run["status"] == "awaiting_selection":
                        await asyncio.sleep(0.1)
                    choice_idx = run["store"]["selections"].get(node, 0)
                    run["status"] = "running"
                selection = HumanSelectionGate().build(
                    options=research["candidates"],
                    engagement_mode=mode_label,
                    selection_index=choice_idx,
                )
                selected_research = selection["selected"]
                segment_output = {
                    "candidates": research["candidates"],
                    "selection": selection,
                }
                await emit(run_id, "exit", {"node": node, "selected": selected_research})
                await record(node, {"query": intake["normalized_query"]}, segment_output)

            elif node == "AnalysisAgent":
                analysis = AnalysisAgent().build(selected_input=selected_research, candidates=None)
                analysis_options = analysis["options"]
                await emit(run_id, "options", {"node": node, "options": analysis_options})
                choice_idx = 0
                if mode_label == "engage_human":
                    run["status"] = "awaiting_selection"
                    await emit(run_id, "awaiting_selection", {"node": node})
                    while run["status"] == "awaiting_selection":
                        await asyncio.sleep(0.1)
                    choice_idx = run["store"]["selections"].get(node, 0)
                    run["status"] = "running"
                selection = HumanSelectionGate().build(
                    options=analysis_options,
                    engagement_mode=mode_label,
                    selection_index=choice_idx,
                )
                selected_analysis = selection["selected"]
                await emit(run_id, "exit", {"node": node, "selected": selected_analysis})
                await record(node, {"selected_input": selected_research}, {"analysis": analysis, "selection": selection})

            elif node == "ValidationAgent":
                validation = ValidationAgent().build(selected_analysis)
                await emit(run_id, "exit", {"node": node, "output": validation})
                await record(node, {"draft": selected_analysis}, validation)

            elif node == "OutputAgent":
                final = OutputAgent().build(analysis_choice=selected_analysis, validation=validation)
                await emit(run_id, "exit", {"node": node, "output": final})
                await record(node, {"analysis_choice": selected_analysis, "validation": validation}, final)
                final_text = final["final_text"]

        run["status"] = "done"
        await emit(run_id, "done", {"final": final_text})
    except Exception as e:
        run["status"] = "error"
        await emit(run_id, "error", {"message": str(e)})

async def _wait_ok(run_id: str):
    # handle pause/stop
    while True:
        run = RUNS[run_id]
        if run["stop"]:
            raise RuntimeError("Stopped by user")
        if not run["paused"]:
            return
        await asyncio.sleep(0.1)
