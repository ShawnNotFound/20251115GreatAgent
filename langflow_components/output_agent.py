from langflow.custom import CustomComponent
from pydantic import BaseModel
from .trace_logger import log_trace

class OutputOut(BaseModel):
    final_text: str

class OutputAgent(CustomComponent):
    display_name = "Output Agent"
    description = "Produces the final, user-facing answer."

    def build(self, analysis_choice: str, validation: dict | None = None) -> dict:
        final_text = f"{analysis_choice}\n\n(Validation: {validation})"
        out = OutputOut(final_text=final_text).model_dump()
        log_trace({"step": "OutputAgent", "kind": "outputs", "data": out})
        return out
