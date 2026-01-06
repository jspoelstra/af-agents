# Copyright (c) Microsoft. All rights reserved.

import asyncio
import os

from agent_framework import ChatAgent, ChatMessage
from agent_framework.azure import AzureAIClient
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import AzureCliCredential
from dotenv import load_dotenv


def _format_tool_args(arguments: object, *, max_len: int = 800) -> str:
    text = str(arguments)
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text


def _ask_yes_no(prompt: str, *, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{prompt} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please enter 'y' or 'n'.")


async def _stream_with_approvals(agent: ChatAgent, *, thread, initial_input: str) -> None:
    """Stream a single user turn, handling one-or-more approval cycles.

    The Responses API can emit `mcp_approval_request` items mid-stream. The agent framework
    surfaces these as `FunctionApprovalRequestContent` objects inside streaming updates.

    When we see approval requests, we:
    1) prompt the human,
    2) send `FunctionApprovalResponseContent` back as the next user message,
    3) resume streaming on the same thread.
    """

    pending_messages: list[ChatMessage] = [ChatMessage(role="user", text=initial_input)]

    while True:
        approval_requests = []

        async for update in agent.run_stream(pending_messages, thread=thread):
            # Print any text deltas as they arrive
            if update.text:
                print(update.text, end="", flush=True)

            # Collect approval requests (can be multiple)
            if update.user_input_requests:
                approval_requests.extend(update.user_input_requests)

        print("\n", flush=True)

        if not approval_requests:
            return

        # Ask the user to approve/reject each request, then submit them in a single follow-up message.
        approval_responses = []
        for req in approval_requests:
            function_call = getattr(req, "function_call", None)
            name = getattr(function_call, "name", "") if function_call else ""
            arguments = getattr(function_call, "arguments", "") if function_call else ""
            server_label = None
            additional = getattr(function_call, "additional_properties", None)
            if isinstance(additional, dict):
                server_label = additional.get("server_label")

            header = f"Approval required for tool '{name}'"
            if server_label:
                header += f" (server_label={server_label})"
            print(header)
            print(f"Arguments: {_format_tool_args(arguments)}")

            approved = _ask_yes_no("Approve this tool call?", default=True)
            approval_responses.append(req.create_response(approved=approved))

        pending_messages = [ChatMessage(role="user", contents=approval_responses)]


async def main() -> None:
    load_dotenv()

    agent_name = os.environ.get("AZURE_AI_AGENT_NAME", "MCPAgentNoAsk")

    async with (
        AzureCliCredential() as credential,
        AIProjectClient(endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"], credential=credential) as project_client,
    ):
        chat_client = AzureAIClient(
            project_client=project_client,
            agent_name=agent_name,
            use_latest_version=True,
        )

        async with ChatAgent(chat_client=chat_client) as agent:
            thread = agent.get_new_thread()

            print(f"Connected. Agent: {agent_name}")
            print("Type your message and press Enter. Type 'exit' or Ctrl+C to quit.\n")

            while True:
                try:
                    user_text = input("User: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting.")
                    return

                if not user_text:
                    continue
                if user_text.lower() in {"exit", "quit"}:
                    return

                print("Agent: ", end="", flush=True)
                await _stream_with_approvals(agent, thread=thread, initial_input=user_text)


if __name__ == "__main__":
    asyncio.run(main())
