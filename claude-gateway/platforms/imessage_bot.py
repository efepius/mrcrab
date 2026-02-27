"""
iMessage adapter via BlueBubbles (https://bluebubbles.app).

Requirements:
  - A Mac running the BlueBubbles server app
  - The Mac must be accessible from this VM
  - Set BLUEBUBBLES_URL and BLUEBUBBLES_PASSWORD in .env

BlueBubbles API docs: https://docs.bluebubbles.app/server/api-reference
"""
import asyncio
import json
import logging

import aiohttp
import websockets

from media.handler import url_to_vision_block
from .base import BasePlatformBot

logger = logging.getLogger(__name__)

PLATFORM = "imessage"


class IMessageBot(BasePlatformBot):
    def __init__(self, session_manager, claude_client, rate_limiter, config):
        super().__init__(session_manager, claude_client, rate_limiter, config)
        self.base_url = config.BLUEBUBBLES_URL.rstrip("/")
        self.password = config.BLUEBUBBLES_PASSWORD
        self._running = False

    @property
    def _params(self):
        return {"password": self.password}

    async def start(self):
        # Verify connection
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/v1/server/info",
                    params=self._params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        logger.error("BlueBubbles connection failed: HTTP %s", resp.status)
                        return
                    info = await resp.json()
                    logger.info(
                        "iMessage connected via BlueBubbles. Server: %s",
                        info.get("data", {}).get("name", "unknown"),
                    )
        except Exception as e:
            logger.error("Cannot connect to BlueBubbles at %s: %s", self.base_url, e)
            return

        self._running = True
        await self._listen_websocket()

    async def stop(self):
        self._running = False

    async def _listen_websocket(self):
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}?password={self.password}"

        while self._running:
            try:
                async with websockets.connect(ws_url) as ws:
                    logger.info("iMessage WebSocket connected.")
                    async for raw in ws:
                        try:
                            event = json.loads(raw)
                            await self._handle_event(event)
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                if self._running:
                    logger.warning("iMessage WebSocket error: %s — reconnecting in 5s", e)
                    await asyncio.sleep(5)

    async def _handle_event(self, event: dict):
        event_type = event.get("type", "")
        if event_type != "new-message":
            return

        data = event.get("data", {})
        # Skip our own outgoing messages
        if data.get("isFromMe"):
            return

        text = data.get("text") or ""
        chat_guid = data.get("chats", [{}])[0].get("guid", "")
        handle = data.get("handle", {})
        sender = handle.get("address", "") or handle.get("id", "unknown")

        media_blocks = None
        attachments = data.get("attachments", [])
        for attachment in attachments:
            mime = attachment.get("mimeType", "")
            if mime.startswith("image/"):
                att_guid = attachment.get("guid", "")
                url = f"{self.base_url}/api/v1/attachment/{att_guid}/download"
                block = await url_to_vision_block(f"{url}?password={self.password}")
                if block:
                    media_blocks = media_blocks or []
                    media_blocks.append(block)

        if not text and not media_blocks:
            return

        response = await self.handle_message(
            platform=PLATFORM,
            user_id=sender,
            display_name=sender,
            text=text or "Please describe the attached image.",
            media_blocks=media_blocks,
        )

        await self._send_message(chat_guid, response)

    async def _send_message(self, chat_guid: str, text: str):
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "chatGuid": chat_guid,
                    "message": text,
                    "method": "apple-script",
                }
                async with session.post(
                    f"{self.base_url}/api/v1/message/send",
                    params=self._params,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status not in (200, 201):
                        logger.warning("BlueBubbles send failed: HTTP %s", resp.status)
        except Exception as e:
            logger.error("Failed to send iMessage: %s", e)
