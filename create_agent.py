# Copyright (c) Microsoft. All rights reserved.
# From azure_ai_with_existing_agent.py found here:
# https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai/azure_ai_with_existing_agent.py

import asyncio
import os

from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity.aio import AzureCliCredential

from dotenv import load_dotenv

"""
Azure AI Agent with MCP Tool Example
This sample demonstrates creating Azure AI Agents with
MCP tools, set up to either require approval for tool calls or not.
Note that the Project must have a GitHub connection already set up
in Foundry for this sample to work.
"""


async def main() -> None:
    # Create the client
    async with (
        AzureCliCredential() as credential,
        AIProjectClient(endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"], credential=credential) as project_client,
    ):
        github_connection_name = "GitHub"
        github_connection_target = None
        async for connection in project_client.connections.list():
            if connection.name == github_connection_name:
                github_connection_target = connection.target
                print(f"Found GitHub connection target: {github_connection_target}")

        if not github_connection_target:
            raise RuntimeError(
                f"Could not find a Project connection named '{github_connection_name}'. "
                "Check the connection name in Foundry or update the script."
            )

        mcp_tool_dict = {
            "type": "mcp",
            "server_label": "GitHubTool",
            # When using a Foundry Project Connection, the MCP server URL is the connection target
            # (often an AI Foundry gateway URL), and the auth is resolved via project_connection_id.
            "server_url": github_connection_target,
            "project_connection_id": github_connection_name,
        }
        # Create agent that does not ask for approval for MCP tool calls
        azure_ai_agent = await project_client.agents.create_version(
            agent_name="MCPAgentNoAsk",
            definition=PromptAgentDefinition(
                model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
                # Setting specific requirements to verify that this agent is used.
                instructions="You are a helpful assistant with access to GitHub.",
                tools=[{**mcp_tool_dict, "require_approval": "never"}],
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
                tools=[{**mcp_tool_dict, "require_approval": "always"}],
            ),  
        )
        print(
            f"Created agent '{azure_ai_agent_ask.name}' version '{azure_ai_agent_ask.version}' with MCP tool with approval."
        )

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
