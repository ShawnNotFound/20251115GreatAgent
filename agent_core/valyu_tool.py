from __future__ import annotations

import os
import requests

VALYU_ENDPOINT = os.environ.get("VALYU_API_URL", "https://api.valyu.ai/search")
VALYU_API_KEY = os.environ.get("VALYU_API_KEY")


def valyu_search(query: str) -> list[str]:
    if not VALYU_API_KEY:
        return [
            f"[Valyu demo] Top finding for {query}",
            f"[Valyu demo] Counterpoint for {query}",
        ]
    headers = {"Authorization": f"Bearer {VALYU_API_KEY}"}
    resp = requests.get(VALYU_ENDPOINT, params={"q": query, "limit": 3}, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("results") or data.get("data") or []
    if isinstance(items, list):
        return [item.get("summary") or item.get("title") or str(item) for item in items[:3]]
    return [str(items)]
