from __future__ import annotations

from langflow.custom import CustomComponent

from langflow_components.__schemas import HumanSelectionOut
from langflow_components.__trace_logger import log_trace


class HumanSelectionGate(CustomComponent):
    display_name = "Human Selection Gate"
    description = "Pauses pipelines for human choice or auto-selects in agent mode."

    def build(
        self,
        options: list[str],
        engagement_mode: str = "agents_only",
        selection_index: int | None = None,
        user_override: str | None = None,
    ) -> dict:
        cleaned = options or []
        mode = (engagement_mode or "agents_only").lower()
        was_auto_selected = mode != "engage_human"

        if user_override:
            selected = user_override
            rationale = "Operator supplied a custom answer."
            was_auto_selected = False
        elif selection_index is not None and 0 <= selection_index < len(cleaned):
            selected = cleaned[selection_index]
            rationale = f"Operator picked option #{selection_index + 1}."
            was_auto_selected = False
        else:
            selected = cleaned[0] if cleaned else ""
            rationale = "Agents-only mode selected the first viable option."

        out = HumanSelectionOut(
            options=cleaned,
            selected=selected,
            was_auto_selected=was_auto_selected,
            rationale=rationale,
        ).model_dump()
        log_trace({"step": "HumanSelectionGate", "kind": "outputs", "data": out})
        return out
