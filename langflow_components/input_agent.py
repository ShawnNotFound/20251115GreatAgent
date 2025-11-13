from __future__ import annotations

from langflow.custom import CustomComponent

from langflow_components.__schemas import IntakeOut
from langflow_components.__trace_logger import log_trace


class InputAgent(CustomComponent):
    display_name = "Intake Agent"
    description = "Normalizes user intent, infers tools, and picks execution mode."

    TOOL_KEYWORDS = {
        "research": ["research", "latest", "compare", "find", "lookup"],
        "analysis": ["analyze", "analysis", "compare", "trade-off", "debate"],
        "validation": ["fact", "validate", "double-check", "verify", "risk"],
        "output": ["summarize", "write", "draft", "response"],
    }

    def build(
        self,
        user_query: str,
        preferred_mode: str = "agents_only",
        guardrails: str | None = None,
    ) -> dict:
        normalized = (user_query or "").strip()
        mode = preferred_mode.lower().replace(" ", "_") or "agents_only"
        if mode not in {"agents_only", "engage_human"}:
            mode = "agents_only"

        tools = self._infer_tools(normalized)
        constraints = self._extract_constraints(normalized, guardrails)

        out = IntakeOut(
            normalized_query=normalized,
            engagement_mode=mode,
            tools_needed=tools,
            constraints=constraints,
        ).model_dump()
        log_trace({"step": "InputAgent", "kind": "outputs", "data": out})
        return out

    def _infer_tools(self, query: str) -> list[str]:
        lowered = query.lower()
        selected: set[str] = set()
        for tool_name, keywords in self.TOOL_KEYWORDS.items():
            if any(word in lowered for word in keywords):
                selected.add(tool_name)
        return sorted(selected) or ["research", "analysis", "validation", "output"]

    def _extract_constraints(self, query: str, guardrails: str | None) -> list[str]:
        constraints: list[str] = []
        if guardrails:
            constraints.append(guardrails.strip())
        lowered = query.lower()
        if "short" in lowered or "concise" in lowered:
            constraints.append("Keep answers concise.")
        if "cite" in lowered or "reference" in lowered:
            constraints.append("Surface references before final answer.")
        if "stop" in lowered:
            constraints.append("Enable stop button before risky steps.")
        return constraints
