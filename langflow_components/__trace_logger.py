from langflow.custom import CustomComponent
import time, json, os

LOG_PATH = os.environ.get("AGF_TRACE_LOG", "/tmp/agentglass_trace.jsonl")

def log_trace(record: dict):
    record["ts"] = time.time()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

class TraceLogger(CustomComponent):
    display_name = "Trace Logger"
    description = "Pass-through that logs inputs/outputs for transparency."

    def build(self, step_name: str, inputs: dict) -> dict:
        # No transform — just log and return
        log_trace({"step": step_name, "kind": "inputs", "data": inputs})
        return inputs
