# af-agents

Simple, minimal examples of creating and running **durable Azure AI Foundry Agents** that can call:

- **MCP (Model Context Protocol)** tools via a Foundry Project connection
- **File Search** against an Azure AI **Vector Store**

This repo focuses on two things:

- **Create** agent versions configured with an MCP tool (example: GitHub MCP via a Foundry Project connection)
- **Run** an agent in a tiny terminal chat loop, including **interactive approval handling** when the agent requests tool-call approval

## What’s in this repo

- `create_vector_store.py` uploads local files and creates a Vector Store in your Project.
- `create_agent.py` creates two agent versions:
  - `MCPAgentNoAsk`: MCP tool calls don’t require approval
  - `MCPAgentAsk`: MCP tool calls always require approval
- `run_agent.py` runs an interactive chat loop against an existing agent and handles approval requests during streaming.

## Prerequisites

- Python 3.10+ (3.11+ recommended)
- An **Azure AI Foundry Project** (Azure AI Projects)
- A **model deployment** available to the Project (you’ll reference it by deployment name)
- Azure CLI authenticated locally:
  - `az login`
- A **Foundry Project connection** that provides an MCP endpoint.
- A **Vector Store** in the Project (for File Search). You can create one with `create_vector_store.py`.

This sample assumes you already have a Project connection named **`GitHub`** configured in Foundry (see `create_agent.py`). If your connection name differs, update the script.

## Getting started

### 1) Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

Note: this repo uses a pre-release of `agent-framework` via `agent-framework --pre`.

### 3) Set environment variables

Both scripts load environment variables via `python-dotenv`, so the easiest path is a local `.env` file.

Copy the example and edit it:

```bash
cp env.sample .env
```

Or create `.env` manually with:

```bash
AZURE_AI_PROJECT_ENDPOINT="https://<your-project-name>.<region>.api.azureml.ms"
AZURE_AI_MODEL_DEPLOYMENT_NAME="<your-model-deployment-name>"

# Vector Store used by the agent's File Search tool
VECTOR_STORE_NAME="my_vectorstore"

# Used by create_vector_store.py
FILE_PATTERNS="resources/*.pdf"
FILE_CONFLICT_ACTION="ask"

# Optional: which agent to run (defaults to MCPAgentNoAsk)
AZURE_AI_AGENT_NAME="MCPAgentNoAsk"
```

Required variables:

- `AZURE_AI_PROJECT_ENDPOINT`: the Foundry Project endpoint
- `AZURE_AI_MODEL_DEPLOYMENT_NAME`: the model deployment name to use in the agent definition

Optional variables:

- `AZURE_AI_AGENT_NAME`: which agent name `run_agent.py` connects to
- `VECTOR_STORE_NAME`: Vector Store name the agent will use for File Search (defaults to `my_vectorstore`)
- `FILE_PATTERNS`: comma-separated glob patterns for local files to upload (defaults to `resources/*.pdf`)
- `FILE_CONFLICT_ACTION`: what to do if a filename already exists (`ask`, `reuse`, `upload`, `overwrite`; defaults to `ask`)

### 4) Create a Vector Store (for File Search)

```bash
python create_vector_store.py
```

This uploads local files (from `FILE_PATTERNS`) and creates a Vector Store named `VECTOR_STORE_NAME`.

### 5) Create agent versions in Foundry

```bash
python create_agent.py
```

This will create/update agent versions named `MCPAgentNoAsk` and `MCPAgentAsk`.

### 6) Run the agent

```bash
python run_agent.py
```

By default it connects to `MCPAgentNoAsk`. To run the approval-flow agent:

```bash
AZURE_AI_AGENT_NAME=MCPAgentAsk python run_agent.py
```

When approvals are required, `run_agent.py` will:

1. display the pending tool call name and arguments
2. prompt you to approve/reject
3. continue streaming the agent response on the same thread

## Customizing the MCP tool

In `create_agent.py`, the MCP tool is configured from a **Foundry Project connection** named `GitHub`.

If you want to use a different connection or a different MCP server:

- Update `github_connection_name` (or rename the variable)
- Update the `server_label`
- If your connection is not named `GitHub`, ensure `project_connection_id` matches the connection name in Foundry

## Troubleshooting

- If `create_agent.py` says it can’t find the `GitHub` connection, confirm the connection name in your Foundry Project and update the script.
- If `create_agent.py` says it can’t find the Vector Store, run `create_vector_store.py` first and confirm `VECTOR_STORE_NAME` matches the Vector Store name in Foundry.
- If authentication fails, re-run `az login` and confirm your account has access to the Foundry Project.
- If the model deployment can’t be found, verify `AZURE_AI_MODEL_DEPLOYMENT_NAME` matches the deployment name in Foundry.

## Contributing

Contributions are welcome.

- Open an issue describing the change (or the bug/feature).
- Keep PRs small and focused.
- If you add new samples, prefer:
  - a single entrypoint script
  - clear environment variable names
  - minimal dependencies

## License

MIT. See `LICENSE`.
