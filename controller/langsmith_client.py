from __future__ import annotations

import os
import requests

LANGSMITH_API_URL = os.environ.get("LANGSMITH_API_URL", "https://api.smith.langchain.com")
LANGSMITH_API_KEY = os.environ.get("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.environ.get("LANGSMITH_PROJECT", "greatagent-demo")


def fetch_recent_traces(limit: int = 5):
    if not LANGSMITH_API_KEY:
        return [
            {
                "id": "demo-1",
                "name": "Mock Run",
                "status": "completed",
                "url": f"https://smith.langchain.com/public/{LANGSMITH_PROJECT}/demo-1",
            }
        ]
    headers = {"x-api-key": LANGSMITH_API_KEY}
    params = {"project_name": LANGSMITH_PROJECT, "limit": limit}
    resp = requests.get(f"{LANGSMITH_API_URL}/runs", headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    runs = data.get("data") or data
    traces = []
    for run in runs[:limit]:
        traces.append(
            {
                "id": run.get("id"),
                "name": run.get("name"),
                "status": run.get("status"),
                "url": run.get("url") or run.get("dashboard_url"),
            }
        )
    return traces
