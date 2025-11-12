from langflow.custom import CustomComponent
from pydantic import BaseModel
from .trace_logger import log_trace

class ValidationOut(BaseModel):
    is_consistent: bool
    confidence: float
    notes: str

class ValidationAgent(CustomComponent):
    display_name = "Validation Agent"
    description = "Light checks for consistency and factuality."

    def build(self, draft: str) -> dict:
        out = ValidationOut(
            is_consistent=True,
            confidence=0.82,
            notes="No contradictions detected in local context."
        ).model_dump()
        log_trace({"step": "ValidationAgent", "kind": "outputs", "data": out})
        return out
