import json
import os
import queue
import threading
import time

import requests
import sseclient
import streamlit as st
from streamlit.components.v1 import iframe

API = "http://localhost:8077"
LANGFLOW_BASE_URL = os.environ.get("LANGFLOW_EMBED_URL", "http://localhost:7860").rstrip("/")
LANGFLOW_FLOW_ID = os.environ.get("LANGFLOW_FLOW_ID")

def build_langflow_embed_url() -> str:
    if LANGFLOW_FLOW_ID:
        return f"{LANGFLOW_BASE_URL}/#/flow/{LANGFLOW_FLOW_ID}?embed=true"
    return LANGFLOW_BASE_URL


def stream_events(run_id: str, event_queue: queue.Queue):
    headers = {"Accept": "text/event-stream"}
    try:
        with requests.get(f"{API}/events/{run_id}", stream=True, headers=headers, timeout=120) as resp:
            client = sseclient.SSEClient(resp)
            for event in client.events():
                event_queue.put((event.event or "message", event.data or ""))
    except Exception as exc:
        event_queue.put(("error", json.dumps({"message": str(exc)})))
    finally:
        event_queue.put(("__listener_done__", run_id))

st.set_page_config(page_title="AgentGlassFlow", layout="wide")
st.title("AgentGlassFlow — Glass-Box Multi-Agent Orchestrator")

main_col, demo_col = st.columns([3, 1], gap="large")

with demo_col:
    st.markdown("#### Workflow Preview (Langflow)")
    if LANGFLOW_FLOW_ID:
        st.caption("Embedded Langflow flow (read-only). Edit in the main Langflow app if needed.")
    else:
        st.warning("Set LANGFLOW_FLOW_ID to a Flow ID so we can show the exact graph.")
    iframe(build_langflow_embed_url(), height=360)

with main_col:
    query = st.text_input("User query", value="Compare Llama-3.1 and GPT-4o for doc summarization.")
    col1, col2 = st.columns(2)
    mode = col1.radio("Mode", ["auto", "human"], horizontal=True)
    start = col2.button("Start run")

    if "run_id" not in st.session_state:
        st.session_state.run_id = None
    if "segments" not in st.session_state:
        st.session_state.segments = {}
    if "workflow" not in st.session_state:
        st.session_state.workflow = {}
    if "trace_lines" not in st.session_state:
        st.session_state.trace_lines = []
    if "pending_options" not in st.session_state:
        st.session_state.pending_options = {}
    if "event_queue" not in st.session_state:
        st.session_state.event_queue = queue.Queue()
    if "listener_thread" not in st.session_state:
        st.session_state.listener_thread = None
    if "listening_run_id" not in st.session_state:
        st.session_state.listening_run_id = None

    if start:
        st.session_state.segments = {}
        st.session_state.workflow = {}
        st.session_state.trace_lines = []
        st.session_state.pending_options = {}
        st.session_state.event_queue = queue.Queue()
        r = requests.post(f"{API}/run", json={"user_query": query, "mode": mode})
        st.session_state.run_id = r.json()["run_id"]
        st.session_state.listening_run_id = st.session_state.run_id
        thread = threading.Thread(
            target=stream_events,
            args=(st.session_state.run_id, st.session_state.event_queue),
            daemon=True,
        )
        thread.start()
        st.session_state.listener_thread = thread

if st.session_state.run_id:
    rid = st.session_state.run_id
    control_col1, control_col2, control_col3 = main_col.columns(3)
    if control_col1.button("Pause"): requests.post(f"{API}/pause/{rid}")
    if control_col2.button("Resume"): requests.post(f"{API}/resume/{rid}")
    if control_col3.button("Stop"): requests.post(f"{API}/stop/{rid}")

    # Drain event queue from background listener
    while not st.session_state.event_queue.empty():
        event_name, raw = st.session_state.event_queue.get()
        if event_name == "__listener_done__":
            st.session_state.listener_thread = None
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}

        if "raw" in payload:
            display_payload = payload["raw"]
        else:
            display_payload = json.dumps(payload, ensure_ascii=False)
        line = f"- **{event_name}**: `{display_payload}`"
        st.session_state.trace_lines.append(line)

        if event_name == "workflow":
            st.session_state.workflow = payload
        elif event_name == "segment":
            st.session_state.segments[payload["node"]] = {
                "input": payload.get("input", {}),
                "output": payload.get("output", {}),
            }
        elif event_name == "options":
            st.session_state.pending_options[payload["node"]] = payload.get("options", [])
        elif event_name == "awaiting_selection" and mode == "human":
            node = payload.get("node", "")
            st.session_state.pending_options.setdefault(node, [])

    main_col.markdown("### Segment Details")
    if st.session_state.segments:
        segment_names = list(st.session_state.segments.keys())
        selected_segment = main_col.selectbox(
            "Select a segment to inspect",
            segment_names,
            index=len(segment_names) - 1,
        )
        segment_data = st.session_state.segments[selected_segment]
        main_col.markdown(f"#### {selected_segment}")
        main_col.markdown("**Inputs**")
        main_col.json(segment_data.get("input", {}))
        main_col.markdown("**Outputs**")
        main_col.json(segment_data.get("output", {}))
    else:
        main_col.info("Segments will appear here once the run starts.")

    if st.session_state.workflow.get("steps"):
        main_col.markdown("### Workflow Timeline")
        for step in st.session_state.workflow["steps"]:
            status = step.get("status", "pending").upper()
            requires = " (human pause)" if step.get("requires_human") else ""
            main_col.write(f"- **{step['agent']}** — {status}{requires}")

    main_col.markdown("### Live Trace")
    trace_box = main_col.empty()
    selection_box = main_col.empty()
    trace_box.markdown("\n".join(st.session_state.trace_lines[-10:]))

    awaiting_nodes = [e for e in st.session_state.pending_options.keys()]
    if awaiting_nodes and mode == "human":
        node = awaiting_nodes[-1]
        opts = st.session_state.pending_options.get(node, [])
        with selection_box:
            st.warning(f"Awaiting selection for **{node}**")
            if opts:
                indices = list(range(len(opts)))
                idx = st.radio(
                    f"Choose output for {node}",
                    indices,
                    index=0,
                    format_func=lambda i: f"{i}: {opts[i]}",
                    key=f"{node}-{int(time.time()*1000)}",
                )
            else:
                idx = 0
            if st.button(f"Confirm {node} selection", key=f"confirm-{node}-{int(time.time()*1000)}"):
                requests.post(f"{API}/select", json={"run_id": rid, "node": node, "choice_index": idx})
                st.session_state.pending_options.pop(node, None)
                st.success(f"Submitted choice {idx} for {node}")

    listener = st.session_state.listener_thread
    if listener and listener.is_alive():
        main_col.caption("Listening for live updates...")
        time.sleep(0.5)
        st.rerun()
