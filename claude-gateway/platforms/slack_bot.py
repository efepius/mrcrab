"""
Slack adapter using slack-bolt (async).

Setup:
  1. Create a Slack app at https://api.slack.com/apps
  2. Enable Socket Mode (simpler — no public URL needed)
  3. Add bot scopes: app_mentions:read, channels:history, im:history,
     im:read, im:write, chat:write, files:read
  4. Enable Events: message.im, app_mention
  5. Get SLACK_BOT_TOKEN (xoxb-...) and SLACK_APP_TOKEN (xapp-...)
"""
import logging

from media.handler import url_to_vision_block
from .base import BasePlatformBot

logger = logging.getLogger(__name__)

PLATFORM = "slack"


class SlackBot(BasePlatformBot):
    def __init__(self, session_manager, claude_client, rate_limiter, config):
        super().__init__(session_manager, claude_client, rate_limiter, config)
        self._app = None
        self._handler = None

    def _build_app(self):
        try:
            from slack_bolt.async_app import AsyncApp
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
        except ImportError:
            raise ImportError(
                "slack-bolt is not installed. Run: pip install slack-bolt"
            )

        app = AsyncApp(token=self.config.SLACK_BOT_TOKEN)

        @app.event("message")
        async def handle_dm(event, say, client):
            # Only handle DMs (channel_type == "im")
            if event.get("channel_type") != "im":
                return
            if event.get("bot_id"):
                return

            await self._process_slack_event(event, say, client)

        @app.event("app_mention")
        async def handle_mention(event, say, client):
            await self._process_slack_event(event, say, client)

        self._app = app
        self._handler = AsyncSocketModeHandler(app, self.config.SLACK_APP_TOKEN)

    async def _process_slack_event(self, event, say, client):
        user_id = event.get("user", "")
        text = event.get("text", "")
        ts = event.get("ts", "")
        channel = event.get("channel", "")

        # Strip bot mention
        if self._app and self._app._client:
            bot_user_id = (await self._app.client.auth_test()).get("user_id", "")
            text = text.replace(f"<@{bot_user_id}>", "").strip()

        # /reset command
        if text.lower() in ("/reset", "reset"):
            self.sessions.reset(PLATFORM, user_id)
            await say("Session reset. Starting fresh.")
            return

        # Get user display name
        try:
            user_info = await client.users_info(user=user_id)
            display_name = (
                user_info["user"]["profile"].get("display_name")
                or user_info["user"]["real_name"]
                or user_id
            )
        except Exception:
            display_name = user_id

        # Handle file attachments (images)
        media_blocks = []
        for file in event.get("files", []):
            mime = file.get("mimetype", "")
            if mime.startswith("image/"):
                url = file.get("url_private_download", "")
                if url:
                    # Slack requires Authorization header for private files
                    import aiohttp
                    try:
                        async with aiohttp.ClientSession(
                            headers={"Authorization": f"Bearer {self.config.SLACK_BOT_TOKEN}"}
                        ) as session:
                            async with session.get(url) as resp:
                                data = await resp.read()
                        from media.handler import bytes_to_vision_block
                        block = await bytes_to_vision_block(data, mime)
                        if block:
                            media_blocks.append(block)
                    except Exception as e:
                        logger.warning("Failed to download Slack file: %s", e)

        response = await self.handle_message(
            platform=PLATFORM,
            user_id=user_id,
            display_name=display_name,
            text=text or "Please describe the attached image.",
            media_blocks=media_blocks or None,
        )

        await say(response)

    async def start(self):
        logger.info("Starting Slack bot (Socket Mode)...")
        self._build_app()
        await self._handler.start_async()

    async def stop(self):
        logger.info("Stopping Slack bot...")
        if self._handler:
            await self._handler.close_async()
