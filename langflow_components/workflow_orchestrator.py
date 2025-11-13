from __future__ import annotations

from langflow.custom import CustomComponent

from langflow_components.__schemas import WorkflowOrchestrationOut, WorkflowStep
from langflow_components.__trace_logger import log_trace


class WorkflowOrchestrator(CustomComponent):
    display_name = "Workflow Orchestrator"
    description = "Turns plans + mode into an executable pipeline timeline."

    def build(
        self,
        workflow_plan: list[str],
        engagement_mode: str = "agents_only",
        tools_needed: list[str] | None = None,
    ) -> dict:
        mode = (engagement_mode or "agents_only").lower()
        steps = self._decorate_steps(workflow_plan, mode)
        control_panel = {
            "mode": mode,
            "tools_confirmed": tools_needed or [],
            "stop_enabled": True,
            "resume_hint": "Switch nodes to edit before resuming execution.",
        }
        out = WorkflowOrchestrationOut(
            mode=mode,
            steps=steps,
            control_panel=control_panel,
        ).model_dump()
        log_trace({"step": "WorkflowOrchestrator", "kind": "outputs", "data": out})
        return out

    def _decorate_steps(self, plan: list[str], mode: str) -> list[WorkflowStep]:
        steps: list[WorkflowStep] = []
        human_mode = mode == "engage_human"
        for idx, agent_name in enumerate(plan or []):
            requires_human = human_mode and agent_name in {"ResearchAgent", "AnalysisAgent"}
            notes = "Await human choice" if requires_human else "Auto-advance when ready"
            steps.append(
                WorkflowStep(
                    agent=agent_name,
                    status="pending" if idx > 0 else "ready",
                    requires_human=requires_human,
                    notes=notes,
                )
            )
        return steps
