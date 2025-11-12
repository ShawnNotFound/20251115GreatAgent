import asyncio, json, uuid, time
from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field

app = FastAPI(title="AgentGlassFlow Controller")

# --- In-memory run state (OK for hackathon)
RUNS: dict[str, dict] = {}
EVENT_QUEUES: dict[str, asyncio.Queue] = {}

class RunMode(str):
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
        "store": {"user_query": req.user_query, "selections": {}},
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
        while RUNS.get(run_id) and RUNS[run_id]["status"] in ("running","paused","awaiting_selection"):
            item = await EVENT_QUEUES[run_id].get()
            yield f"event: {item['event']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
        yield f"event: end\ndata: {{\"run_id\":\"{run_id}\"}}\n\n"
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
    try:
        # Step 1: TaskDecomposer
        await _wait_ok(run_id)
        await emit(run_id, "enter", {"node": "TaskDecomposer"})
        plan = ["ResearchAgent", "AnalysisAgent", "ValidationAgent", "OutputAgent"]
        await emit(run_id, "exit", {"node": "TaskDecomposer", "output": {"workflow_plan": plan}})

        # Step 2: ResearchAgent (multi-output)
        await _wait_ok(run_id)
        await emit(run_id, "enter", {"node": "ResearchAgent"})
        candidates = ["[A] Focused", "[B] Broad", "[C] Counterpoints"]
        await emit(run_id, "candidates", {"node": "ResearchAgent", "candidates": candidates})

        choice_idx = 0
        if run["mode"] == "human":
            run["status"] = "awaiting_selection"
            await emit(run_id, "awaiting_selection", {"node": "ResearchAgent"})
            # Wait until /select sets a choice for this node
            while run["status"] == "awaiting_selection":
                await asyncio.sleep(0.1)
            choice_idx = run["store"]["selections"].get("ResearchAgent", 0)
        await emit(run_id, "exit", {"node": "ResearchAgent", "selected": candidates[choice_idx]})

        # Step 3: AnalysisAgent (multi-output)
        await _wait_ok(run_id)
        await emit(run_id, "enter", {"node": "AnalysisAgent"})
        options = ["Concise reasoning", "Detailed trade-offs"]
        await emit(run_id, "options", {"node": "AnalysisAgent", "options": options})
        choice_idx = 0
        if run["mode"] == "human":
            run["status"] = "awaiting_selection"
            await emit(run_id, "awaiting_selection", {"node": "AnalysisAgent"})
            while run["status"] == "awaiting_selection":
                await asyncio.sleep(0.1)
            choice_idx = run["store"]["selections"].get("AnalysisAgent", 0)
        await emit(run_id, "exit", {"node": "AnalysisAgent", "selected": options[choice_idx]})

        # Step 4: ValidationAgent
        await _wait_ok(run_id)
        await emit(run_id, "enter", {"node": "ValidationAgent"})
        validation = {"is_consistent": True, "confidence": 0.82}
        await emit(run_id, "exit", {"node": "ValidationAgent", "output": validation})

        # Step 5: OutputAgent
        await _wait_ok(run_id)
        await emit(run_id, "enter", {"node": "OutputAgent"})
        final_text = f"{options[choice_idx]}\n\n(Validation: {validation})"
        await emit(run_id, "exit", {"node": "OutputAgent", "final": final_text})

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
