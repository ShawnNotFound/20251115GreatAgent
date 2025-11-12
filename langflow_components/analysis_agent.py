from langflow.custom import CustomComponent
from pydantic import BaseModel
from .trace_logger import log_trace

class AnalysisOut(BaseModel):
    options: list[str]
    rationale: str

class AnalysisAgent(CustomComponent):
    display_name = "Analysis Agent"
    description = "Compares candidates and proposes reasoned options."

    def build(self, selected_input: str | None = None, candidates: list[str] | None = None) -> dict:
        source = selected_input or (candidates[0] if candidates else "")
        options = [
            f"Concise reasoning based on: {source}",
            f"Detailed trade-offs based on: {source}",
        ]
        out = AnalysisOut(
            options=options,
            rationale="Compared alternatives and distilled trade-offs."
        ).model_dump()
        log_trace({"step": "AnalysisAgent", "kind": "outputs", "data": out})
        return out
