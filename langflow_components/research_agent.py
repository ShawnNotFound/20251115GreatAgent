from langflow.custom import CustomComponent
from pydantic import BaseModel
from .trace_logger import log_trace

class ResearchOut(BaseModel):
    candidates: list[str]

class ResearchAgent(CustomComponent):
    display_name = "Research Agent"
    description = "Gathers info and returns multiple candidates."

    def build(self, query: str) -> dict:
        # Replace with actual search + LLM summarization
        candidates = [
            f"[A] Focused answer for: {query}",
            f"[B] Broader context for: {query}",
            f"[C] Counterpoints about: {query}",
        ]
        out = ResearchOut(candidates=candidates).model_dump()
        log_trace({"step": "ResearchAgent", "kind": "outputs", "data": out})
        return out
