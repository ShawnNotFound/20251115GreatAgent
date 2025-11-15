# GreatAgent — LangChain + Bedrock Demo

This repo now demonstrates a multi-agent workflow powered by **Claude 3.5 Sonnet on AWS Bedrock**, **LangChain** tooling, a Valyu search tool, and **LangSmith** tracing. The backend builds a mini orchestrator that walks through Intake → Task Decomposition → Workflow planning → Research → Analysis → Validation → Output, and the React dashboard streams each step while also showing LangSmith traces.

## Architecture

- `agent_core/bedrock_client.py` — thin wrapper around Bedrock's Claude 3.5 Sonnet (falls back to demo text if AWS creds are missing).
- `agent_core/pipeline.py` — LangChain-style helper that prompts Claude for each agent stage and uses Valyu for search.
- `controller/server.py` — FastAPI controller that runs the pipeline, emits SSE events, fetches LangSmith traces, and exposes configuration endpoints.
- `controller/langsmith_client.py` — pulls recent traces for the dashboard.
- `greatagent-ui/` — React + Vite + ReactFlow dashboard with a LangSmith trace panel, pipeline editor, and live stream view.

## Configuration

Create or edit `.env` in the repo root (a template is already checked in). Important variables:

| Variable | Purpose |
| --- | --- |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Needed to call Claude on Bedrock. When omitted, the app runs in demo mode with placeholder responses. |
| `CLAUDE_MODEL` | Bedrock model ID (default `anthropic.claude-3-5-sonnet-20240620-v1:0`). |
| `VALYU_API_KEY`, `VALYU_API_URL` | Credentials for the Valyu search API. Demo snippets are used when missing. |
| `LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` | Standard LangSmith env vars. When set, every LangChain call automatically pushes traces. |
| `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_API_URL`, `LANGSMITH_DASHBOARD_URL` | Used by our `/traces` endpoint and to build shareable trace links. |

You can still edit per-agent prompts/model IDs from the dashboard (Agent Settings panel) — they’re stored in `agent_settings.json` via the existing settings store.

## Running the demo

1. **Install deps** (Python 3.11+ recommended):
   ```bash
   pip install -r requirements.txt
   cd greatagent-ui && npm install && cd ..
   ```
2. **Start the backend**:
   ```bash
   uvicorn controller.server:app --reload --port 8077
   ```
3. **Start the frontend**:
   ```bash
   cd greatagent-ui
   npm run dev
   ```
4. Open the dashboard (default http://localhost:5173). Enter a query and click **Start**. Each stage streams into the UI, and the **LangSmith Traces** panel links to the latest trace (demo URLs when LangSmith isn’t configured).

## LangSmith dashboard data

- Every run emits a `trace` event with the shareable URL from `AgentPipeline.start_trace()`.
- The new `/traces` endpoint aggregates recent runs via the LangSmith API. The React dashboard polls it whenever a run completes and lists the latest trace cards.

## Notes

- Claude / Valyu calls fall back to deterministic demo output when credentials are missing, so you can preview the UX without real keys.
- The ReactFlow canvas is still editable and prettier than before; save layout + plan to customize future runs.
- Agent API settings are optional in this demo but remain editable so you can point specific stages at bespoke microservices later.
