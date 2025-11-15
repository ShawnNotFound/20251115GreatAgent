from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

load_dotenv()

SETTINGS_PATH = Path(os.environ.get("AGENT_SETTINGS_PATH", "agent_settings.json"))

AGENT_ENV_PREFIXES = {
    "InputAgent": "INPUT_AGENT",
    "TaskDecomposer": "TASK_DECOMPOSER",
    "WorkflowOrchestrator": "WORKFLOW_ORCHESTRATOR",
    "ResearchAgent": "RESEARCH_AGENT",
    "AnalysisAgent": "ANALYSIS_AGENT",
    "ValidationAgent": "VALIDATION_AGENT",
    "OutputAgent": "OUTPUT_AGENT",
}

AGENT_CONFIG_FIELDS = ("api_base", "api_key", "model", "prompt")
REQUIRED_FIELDS = ("api_base", "api_key")

DEFAULT_PROMPTS = {
    "InputAgent": "You are the Input Agent. Normalize the user query, infer execution mode, and list guardrails.",
    "TaskDecomposer": "Break the normalized query into a sequenced plan of agents and tools.",
    "WorkflowOrchestrator": "Decorate the plan with statuses, control metadata, and human-in-the-loop flags.",
    "ResearchAgent": "Gather multiple perspectives from the web or docs and summarize each candidate.",
    "AnalysisAgent": "Compare the research candidates and produce reasoned answer options.",
    "ValidationAgent": "Fact-check the preferred answer, track confidence, and highlight gaps.",
    "OutputAgent": "Compose the final response with validation notes and operator reminders.",
}


def _build_defaults() -> Dict[str, Dict[str, str]]:
    data: Dict[str, Dict[str, str]] = {}
    for agent, prefix in AGENT_ENV_PREFIXES.items():
        data[agent] = {
            "api_base": os.environ.get(f"{prefix}_API_BASE", ""),
            "api_key": os.environ.get(f"{prefix}_API_KEY", ""),
            "model": os.environ.get(f"{prefix}_MODEL", ""),
            "prompt": os.environ.get(f"{prefix}_PROMPT", DEFAULT_PROMPTS.get(agent, "")),
        }
    return data


def _load_from_disk() -> Dict[str, Dict[str, str]]:
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
                if isinstance(payload, dict):
                    return payload
        except json.JSONDecodeError:
            pass
    return _build_defaults()


def _persist(settings: Dict[str, Dict[str, str]]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, ensure_ascii=False, indent=2)


_SETTINGS = _load_from_disk()


def get_agent_settings() -> Dict[str, Dict[str, str]]:
    return deepcopy(_SETTINGS)


def update_agent_settings(updates: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    for agent, config in updates.items():
        if agent not in AGENT_ENV_PREFIXES:
            continue
        for field in AGENT_CONFIG_FIELDS:
            if field in config:
                value = config[field]
                _SETTINGS[agent][field] = value if isinstance(value, str) else ""
    _persist(_SETTINGS)
    return get_agent_settings()


def find_missing_agent_settings(agent_ids: list[str] | None = None, required_fields = REQUIRED_FIELDS):
    missing: list[dict[str, Any]] = []
    selected_agents = agent_ids or list(_SETTINGS.keys())
    for agent in selected_agents:
        config = _SETTINGS.get(agent, {})
        missing_fields = [
            field for field in required_fields
            if not str(config.get(field, "")).strip()
        ]
        if missing_fields:
            missing.append({"agent": agent, "fields": missing_fields})
    return missing
