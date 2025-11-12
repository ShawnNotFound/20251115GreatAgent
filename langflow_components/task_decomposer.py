from langflow.custom import CustomComponent
from pydantic import BaseModel, Field
import json
from .trace_logger import log_trace

class DecomposeOut(BaseModel):
    workflow_plan: list[str] = Field(..., description="Agent names in order")

class TaskDecomposer(CustomComponent):
    display_name = "Task Decomposer"
    description = "Turns a user query into a multi-agent plan."

    def build(self, user_query: str) -> dict:
        # Simple heuristic; upgrade with LLM later
        plan = ["ResearchAgent", "AnalysisAgent", "ValidationAgent", "OutputAgent"]
        out = DecomposeOut(workflow_plan=plan)
        log_trace({
            "step": "TaskDecomposer",
            "kind": "outputs",
            "data": out.model_dump()
        })
        return out.model_dump()
