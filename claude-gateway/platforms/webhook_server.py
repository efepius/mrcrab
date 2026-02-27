"""
Webhook HTTP server — lets external services trigger Mr. Crab via HTTP POST.

POST /webhook
  Headers: X-Webhook-Token: <WEBHOOK_TOKEN>
  Body (JSON):
    {
      "message": "What is the weather today?",
      "user_id": "automation",        // optional, defaults to "webhook"
      "platform": "webhook",          // optional
      "reply_url": "https://..."      // optional: POST response back here
    }

Response: {"response": "..."}

Use cases:
  - Trigger Claude from cron jobs
  - Pipe external alerts into Claude for analysis
  - GitHub/PagerDuty/Zapier webhooks
"""
import asyncio
import logging

import aiohttp
from aiohttp import web

from .base import BasePlatformBot

logger = logging.getLogger(__name__)

PLATFORM = "webhook"


class WebhookServer(BasePlatformBot):
    def __init__(self, session_manager, claude_client, rate_limiter, config):
        super().__init__(session_manager, claude_client, rate_limiter, config)
        self._app = web.Application()
        self._runner = None
        self._app.router.add_post("/webhook", self._handle_webhook)
        self._app.router.add_get("/health", self._handle_health)

    async def start(self):
        port = getattr(self.config, "WEBHOOK_PORT", 8787)
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", port)
        await site.start()
        logger.info("Webhook server listening on http://127.0.0.1:%d/webhook", port)

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "bot": "Mr. Crab"})

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        # Token auth
        token = request.headers.get("X-Webhook-Token", "")
        expected = getattr(self.config, "WEBHOOK_TOKEN", "")
        if expected and token != expected:
            return web.json_response({"error": "Unauthorized"}, status=401)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        message = body.get("message", "").strip()
        if not message:
            return web.json_response({"error": "Missing 'message' field"}, status=400)

        user_id = body.get("user_id", "webhook")
        platform = body.get("platform", PLATFORM)
        reply_url = body.get("reply_url", "")

        response = await self.handle_message(
            platform=platform,
            user_id=user_id,
            display_name=user_id,
            text=message,
        )

        # Optionally POST response to a callback URL
        if reply_url:
            asyncio.create_task(self._post_reply(reply_url, response))

        return web.json_response({"response": response})

    async def _post_reply(self, url: str, text: str):
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={"response": text}, timeout=aiohttp.ClientTimeout(total=10))
        except Exception as e:
            logger.warning("Failed to POST reply to %s: %s", url, e)
