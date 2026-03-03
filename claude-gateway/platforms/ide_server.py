"""
IDE WebSocket server — lets IDE extensions (VS Code, JetBrains, etc.) connect to Mr. Crab.

Connect via WebSocket at ws://127.0.0.1:{IDE_PORT}/ide

Authentication:
  First message must be: {"type": "auth", "token": "<IDE_TOKEN>"}

Send messages:
  {
    "type": "message",
    "text": "Explain this function",
    "file": "src/main.py",          // optional: current file path
    "selection": "def foo(): ...",   // optional: selected code
    "language": "python"             // optional: file language
  }

Receive responses:
  {"type": "response", "text": "..."}
  {"type": "error", "text": "..."}

Use cases:
  - Ask Claude about code from your editor
  - Get explanations, refactors, and suggestions with full file context
  - Real-time streaming-style interaction via WebSocket
"""
import asyncio
import json
import logging

from aiohttp import web, WSMsgType

from .base import BasePlatformBot

logger = logging.getLogger(__name__)

PLATFORM = "ide"


class IDEServer(BasePlatformBot):
    def __init__(self, session_manager, claude_client, rate_limiter, config):
        super().__init__(session_manager, claude_client, rate_limiter, config)
        self._app = web.Application()
        self._runner = None
        self._app.router.add_get("/ide", self._handle_ws)
        self._app.router.add_get("/health", self._handle_health)

    async def start(self):
        port = getattr(self.config, "IDE_PORT", 8788)
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", port)
        await site.start()
        logger.info("IDE server listening on ws://127.0.0.1:%d/ide", port)

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "bot": "Mr. Crab", "platform": "ide"})

    async def _handle_ws(self, request: web.Request) -> web.StreamResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        authenticated = False
        expected_token = getattr(self.config, "IDE_TOKEN", "")
        user_id = "ide-user"

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except (json.JSONDecodeError, TypeError):
                    await ws.send_json({"type": "error", "text": "Invalid JSON"})
                    continue

                msg_type = data.get("type", "")

                # Auth must come first
                if not authenticated:
                    if msg_type != "auth":
                        await ws.send_json({"type": "error", "text": "Send auth first: {\"type\": \"auth\", \"token\": \"...\"}"})
                        continue
                    if expected_token and data.get("token") != expected_token:
                        await ws.send_json({"type": "error", "text": "Invalid token"})
                        await ws.close()
                        break
                    authenticated = True
                    user_id = data.get("user_id", "ide-user")
                    await ws.send_json({"type": "auth_ok"})
                    continue

                if msg_type == "message":
                    text = data.get("text", "").strip()
                    if not text:
                        await ws.send_json({"type": "error", "text": "Empty message"})
                        continue

                    # Build context from IDE metadata
                    context_parts = []
                    if data.get("file"):
                        context_parts.append(f"[File: {data['file']}]")
                    if data.get("language"):
                        context_parts.append(f"[Language: {data['language']}]")
                    if data.get("selection"):
                        context_parts.append(f"[Selected code]\n```\n{data['selection']}\n```")

                    if context_parts:
                        text = "\n".join(context_parts) + "\n\n" + text

                    response = await self.handle_message(
                        platform=PLATFORM,
                        user_id=user_id,
                        display_name=user_id,
                        text=text,
                    )
                    await ws.send_json({"type": "response", "text": response})
                else:
                    await ws.send_json({"type": "error", "text": f"Unknown message type: {msg_type}"})

            elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break

        logger.info("IDE client disconnected: %s", user_id)
        return ws
