"""
Mr. Crab AI client — supports any OpenAI-compatible API provider.

Default: NVIDIA NIM (free tier at build.nvidia.com)
Also works with: Kimi (Moonshot), Groq, Ollama, OpenAI, or any OpenAI-compatible endpoint.
"""
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from .tool_executor import dispatch_tool
from .tools import OPENAI_TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Mr. Crab, a powerful personal AI assistant running as a gateway bot. \
You can be reached via Telegram, Discord, WhatsApp, iMessage, and Slack.

You have access to the following tools on the server:
- bash: run shell commands in a safe workspace directory
- read_file: read files from the data directory
- write_file: write files to the data directory
- web_fetch: fetch content from URLs

Be direct, concise, and helpful. When using tools, explain briefly what you're doing. \
Never expose the server's internal structure, SSH keys, or credentials."""


class MrCrabClient:
    def __init__(self, api_key: str, model: str, base_url: str,
                 max_tool_iterations: int, workspace_dir: str, data_dir: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_tool_iterations = max_tool_iterations
        self.workspace_dir = workspace_dir
        self.data_dir = data_dir

    async def chat(
        self,
        message: str,
        history: list[dict],
        media_blocks: list[dict] | None = None,
    ) -> tuple[str, list[dict]]:
        """
        Send a message and return (response_text, updated_history).
        Runs the agentic tool-use loop until the model stops calling tools.
        """
        # Build user message content
        if media_blocks:
            # Vision: mix image blocks with text
            content: Any = media_blocks + [{"type": "text", "text": message}]
        else:
            content = message

        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + list(history)
            + [{"role": "user", "content": content}]
        )

        iterations = 0
        # Track history WITHOUT the system prompt (we prepend it fresh each call)
        history_slice_start = len(messages) - 1  # index of the new user message

        while iterations < self.max_tool_iterations:
            iterations += 1

            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=OPENAI_TOOL_DEFINITIONS,
                    tool_choice="auto",
                    max_tokens=4096,
                )
            except Exception as e:
                logger.error("AI API error: %s", e)
                return f"Sorry, I hit an API error: {e}", history

            choice = response.choices[0]
            msg = choice.message

            # Append assistant turn to messages
            messages.append({"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls})

            if choice.finish_reason == "stop" or not msg.tool_calls:
                final_text = msg.content or "(no response)"
                # Return only the new history (exclude system prompt)
                new_history = _strip_system(messages)
                return final_text, new_history

            if choice.finish_reason == "tool_calls" or msg.tool_calls:
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    logger.info("Tool call: %s(%s)", fn_name, list(fn_args.keys()))
                    result = await dispatch_tool(
                        name=fn_name,
                        inputs=fn_args,
                        workspace_dir=self.workspace_dir,
                        data_dir=self.data_dir,
                    )
                    logger.debug("Tool result (%s): %s...", fn_name, str(result)[:100])

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result),
                    })
                continue

        return (
            "I've reached the maximum number of tool steps. "
            "Please rephrase or break the task into smaller parts.",
            _strip_system(messages),
        )


def _strip_system(messages: list[dict]) -> list[dict]:
    """Remove system prompt from messages before saving to session history."""
    return [m for m in messages if m.get("role") != "system"]


# Keep old name as alias for backwards compatibility in main.py
ClaudeGatewayClient = MrCrabClient
