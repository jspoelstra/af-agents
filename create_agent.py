# Copyright (c) Microsoft. All rights reserved.
# From samples found here:
# https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai

import asyncio
import os

from azure.ai.agents.aio import AgentsClient
from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity.aio import AzureCliCredential

from dotenv import load_dotenv

"""
Azure AI Agent with MCP Tool and File Search Tool Example
This sample demonstrates creating Azure AI Agents with "File Search and
MCP tools, set up to either require approval for tool calls or not.
Note that the Project must have 
1. a GitHub connection and
2. a Vector Store
already set up in Foundry for this sample to work.
The vector store can be created using the create_vector_store.py sample.
"""

async def get_file_search_tool(name: str, agents_client: AgentsClient) -> dict:
    """Gets a file search tool dictionary for the given vector store (Index) name."""

    vector_store_id = None
    async for vs in agents_client.vector_stores.list(limit=100):
        if getattr(vs, "name", None) == name:
            vector_store_id = vs.id
            print(f"Found vector store ID: {vector_store_id} for name: {name}")
            break

    if not vector_store_id:
        raise RuntimeError(
            f"Could not find a Vector Store named '{name}'. "
            "Check the vector store name in Foundry or update the script."
        )

    # IMPORTANT: Azure AI Projects expects the file search tool to be specified as an Azure tool
    # (type=file_search) with vector_store_ids, not the agent-framework HostedFileSearchTool.
    file_search_tool_dict = {
        "type": "file_search",
        "vector_store_ids": [vector_store_id],
        # Optional tuning:
        # "max_num_results": 10,
    }
    return file_search_tool_dict


async def get_mcp_tool(name: str, project_client: AIProjectClient) -> dict:
    """Gets the MCP tool dictionary for the given connection name."""

    mcp_connection_target = None
    async for connection in project_client.connections.list():
        if connection.name == name:
            mcp_connection_target = connection.target
            print(f"Found MCP connection target: {mcp_connection_target}")

    if not mcp_connection_target:
        raise RuntimeError(
            f"Could not find a Project connection named '{name}'. "
            "Check the connection name in Foundry or update the script."
        )

    mcp_tool_dict = {
        "type": "mcp",
        "server_label": "GitHubTool",
        # When using a Foundry Project Connection, the MCP server URL is the connection target
        # (often an AI Foundry gateway URL), and the auth is resolved via project_connection_id.
        "server_url": mcp_connection_target,
        "project_connection_id": name,
    }
    return mcp_tool_dict


async def main() -> None:
    # Create the client
    async with (
        AzureCliCredential() as credential,
        AIProjectClient(endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"], credential=credential) as project_client,
        AgentsClient(endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"], credential=credential) as agents_client,
    ):
        mcp_tool_dict = await get_mcp_tool("GitHub", project_client)
        vector_store_name = os.environ.get("VECTOR_STORE_NAME", "my_vectorstore")
        file_search_tool_dict = await get_file_search_tool(vector_store_name, agents_client)

        # Create agent that does not ask for approval for MCP tool calls
        azure_ai_agent = await project_client.agents.create_version(
            agent_name="MCPAgentNoAsk",
            definition=PromptAgentDefinition(
                model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
                # Setting specific requirements to verify that this agent is used.
                instructions="You are a helpful assistant with access to GitHub.",
                tools=[
                    {**mcp_tool_dict, "require_approval": "never"},
                    file_search_tool_dict
                    ],
            ),
        )
        print(
            f"Created agent '{azure_ai_agent.name}' version '{azure_ai_agent.version}' with MCP tool without approval."
        )
        # Create agent that asks for approval for MCP tool calls
        azure_ai_agent_ask = await project_client.agents.create_version(
            agent_name="MCPAgentAsk",
            definition=PromptAgentDefinition(
                model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
                # Setting specific requirements to verify that this agent is used.
                instructions="You are a helpful assistant with access to GitHub.",
                tools=[
                    {**mcp_tool_dict, "require_approval": "always"}, 
                    file_search_tool_dict
                    ],
            ),  
        )
        print(
            f"Created agent '{azure_ai_agent_ask.name}' version '{azure_ai_agent_ask.version}' with MCP tool with approval."
        )

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
