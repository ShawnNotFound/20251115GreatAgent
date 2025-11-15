from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict

from agent_core.bedrock_client import ClaudeClient
from agent_core.prompts import (
    ANALYSIS_PROMPT,
    DECOMPOSE_PROMPT,
    INPUT_PROMPT,
    OUTPUT_PROMPT,
    RESEARCH_PROMPT,
    VALIDATION_PROMPT,
    WORKFLOW_PROMPT,
)
from agent_core.valyu_tool import valyu_search


class AgentPipeline:
    def __init__(self) -> None:
        self.claude = ClaudeClient()
        self.demo_trace = os.environ.get("LANGSMITH_DEMO_URL", "https://smith.langchain.com/public/demo")

    def _invoke(self, prompt: str) -> Dict[str, Any]:
        response = self.claude.complete(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # fallback by wrapping response
            return {"text": response}

    def run_input(self, user_query: str, preferred_mode: str, guardrails: str | None) -> Dict[str, Any]:
        prompt = INPUT_PROMPT.format(user_query=user_query, mode=preferred_mode, guardrails=guardrails or "none")
        data = self._invoke(prompt)
        return {
            "normalized_query": data.get("normalized_query", user_query.strip()),
            "engagement_mode": data.get("engagement_mode", preferred_mode),
            "tools_needed": data.get("tools_needed", ["research", "analysis", "validation", "output"]),
            "constraints": data.get("constraints", []),
        }

    def run_decomposer(self, normalized_query: str, tools: list[str], constraints: list[str]) -> Dict[str, Any]:
        prompt = DECOMPOSE_PROMPT.format(query=normalized_query, tools=tools, constraints=constraints)
        data = self._invoke(prompt)
        plan = data.get("workflow_plan") or ["ResearchAgent", "AnalysisAgent", "ValidationAgent", "OutputAgent"]
        return {"workflow_plan": plan}

    def run_workflow(self, plan: list[str], mode: str) -> Dict[str, Any]:
        prompt = WORKFLOW_PROMPT.format(plan=plan, mode=mode)
        data = self._invoke(prompt)
        steps = data.get("steps") or [
            {"agent": agent, "notes": "Auto-generated", "requires_human": agent in {"ResearchAgent", "AnalysisAgent"}}
            for agent in plan
        ]
        control_panel = data.get("control_panel") or {"mode": mode}
        return {"steps": steps, "control_panel": control_panel}

    def run_research(self, query: str) -> Dict[str, Any]:
        snippets = valyu_search(query)
        prompt = RESEARCH_PROMPT.format(query=query, snippets=snippets)
        data = self._invoke(prompt)
        candidates = data.get("candidates") or snippets
        return {"candidates": candidates}

    def run_analysis(self, candidates: list[str]) -> Dict[str, Any]:
        prompt = ANALYSIS_PROMPT.format(candidates=candidates)
        data = self._invoke(prompt)
        options = data.get("options") or candidates
        rationale = data.get("rationale", "Demo rationale")
        return {"options": options, "rationale": rationale}

    def run_validation(self, draft: str) -> Dict[str, Any]:
        prompt = VALIDATION_PROMPT.format(draft=draft)
        data = self._invoke(prompt)
        return {
            "is_consistent": data.get("is_consistent", True),
            "confidence": data.get("confidence", 0.8),
            "notes": data.get("notes", "Demo validation"),
        }

    def run_output(self, option: str, validation: Dict[str, Any]) -> Dict[str, Any]:
        prompt = OUTPUT_PROMPT.format(option=option, validation=validation)
        data = self._invoke(prompt)
        return {"final_text": data.get("final_text", option)}

    def start_trace(self) -> Dict[str, str]:
        trace_id = uuid.uuid4().hex
        base_url = os.environ.get("LANGSMITH_DASHBOARD_URL", self.demo_trace)
        return {
            "trace_id": trace_id,
            "trace_url": f"{base_url.rstrip('/')}/runs/{trace_id}",
        }
