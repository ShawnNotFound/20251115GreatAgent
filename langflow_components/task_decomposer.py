from langflow.custom import CustomComponent

from langflow_components.__schemas import DecomposeOut
from langflow_components.__trace_logger import log_trace


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
