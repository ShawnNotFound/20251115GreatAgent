import streamlit as st
import requests, sseclient, time

API = "http://localhost:8077"

st.set_page_config(page_title="AgentGlassFlow", layout="wide")
st.title("AgentGlassFlow — Glass-Box Multi-Agent Orchestrator")

query = st.text_input("User query", value="Compare Llama-3.1 and GPT-4o for doc summarization.")
col1, col2 = st.columns(2)
mode = col1.radio("Mode", ["auto", "human"], horizontal=True)
start = col2.button("Start run")

if "run_id" not in st.session_state: st.session_state.run_id = None

if start:
    r = requests.post(f"{API}/run", json={"user_query": query, "mode": mode})
    st.session_state.run_id = r.json()["run_id"]

if st.session_state.run_id:
    rid = st.session_state.run_id
    c1, c2, c3 = st.columns(3)
    if c1.button("Pause"): requests.post(f"{API}/pause/{rid}")
    if c2.button("Resume"): requests.post(f"{API}/resume/{rid}")
    if c3.button("Stop"): requests.post(f"{API}/stop/{rid}")

    st.markdown("### Live Trace")
    trace_box = st.empty()

    # SSE stream
    resp = requests.get(f"{API}/events/{rid}", stream=True)
    client = sseclient.SSEClient(resp)
    pending_selection_node = None

    for event in client.events():
        data = event.data
        trace_box.write(f"**{event.event}**: `{data}`")
        if event.event == "awaiting_selection" and mode == "human":
            node = eval(data).get("node", "")
            pending_selection_node = node
            st.info(f"Awaiting selection for **{node}**")
            if node == "ResearchAgent":
                idx = st.radio("Pick a candidate (ResearchAgent)", [0,1,2], index=0, horizontal=True, key=f"ra-{time.time()}")
                if st.button("Confirm Research Selection"):
                    requests.post(f"{API}/select", json={"run_id": rid, "node": node, "choice_index": idx})
            if node == "AnalysisAgent":
                idx = st.radio("Pick an option (AnalysisAgent)", [0,1], index=0, horizontal=True, key=f"aa-{time.time()}")
                if st.button("Confirm Analysis Selection"):
                    requests.post(f"{API}/select", json={"run_id": rid, "node": node, "choice_index": idx})
        if event.event in ("done","error","end","stopping"):
            break
