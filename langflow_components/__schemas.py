from __future__ import annotations

from pydantic import BaseModel, Field


class DecomposeOut(BaseModel):
    workflow_plan: list[str] = Field(
        ...,
        description="Ordered list of agent components to execute.",
    )


class ResearchOut(BaseModel):
    candidates: list[str] = Field(
        default_factory=list,
        description="Candidate research summaries surfaced to the analysis agent.",
    )


class AnalysisOut(BaseModel):
    options: list[str] = Field(
        default_factory=list,
        description="Reasoned answer variants to hand off to validation/output agents.",
    )
    rationale: str = Field(
        default="",
        description="Short explanation of how the options were derived.",
    )


class ValidationOut(BaseModel):
    is_consistent: bool = Field(
        default=True,
        description="Indicates whether upstream outputs align without contradictions.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the validation judgment.",
    )
    notes: str = Field(
        default="",
        description="Additional context for human review.",
    )


class OutputOut(BaseModel):
    final_text: str = Field(
        default="",
        description="Final user-facing response after orchestration completes.",
    )


class IntakeOut(BaseModel):
    normalized_query: str = Field(
        ...,
        description="Trimmed, standardized version of the user request.",
    )
    engagement_mode: str = Field(
        default="agents_only",
        description="Execution style, e.g., agents_only or engage_human.",
    )
    tools_needed: list[str] = Field(
        default_factory=list,
        description="Rough tool categories inferred from the query.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Safety or execution constraints detected in the prompt.",
    )


class WorkflowStep(BaseModel):
    agent: str = Field(..., description="Name of the downstream agent node.")
    status: str = Field(
        default="pending",
        description="Execution status placeholder for the UI timeline.",
    )
    requires_human: bool = Field(
        default=False,
        description="Whether this step pauses for human selection in engage mode.",
    )
    notes: str = Field(
        default="",
        description="Extra context surfaced to the operator.",
    )


class WorkflowOrchestrationOut(BaseModel):
    mode: str = Field(..., description="Currently selected engagement mode.")
    steps: list[WorkflowStep] = Field(
        default_factory=list,
        description="Timeline of planned agent executions.",
    )
    control_panel: dict = Field(
        default_factory=dict,
        description="Misc settings (stop button state, resume hints, etc).",
    )


class HumanSelectionOut(BaseModel):
    options: list[str] = Field(
        default_factory=list,
        description="Options shown to the operator or auto-decided.",
    )
    selected: str = Field(
        default="",
        description="Winner passed to the next agent.",
    )
    was_auto_selected: bool = Field(
        default=False,
        description="True if agents-only mode picked for the user.",
    )
    rationale: str = Field(
        default="",
        description="Why the selection was made or what to review.",
    )
