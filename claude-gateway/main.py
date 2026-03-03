"""
Mr. Crab — Claude AI Gateway Bot
Connects Telegram, Discord, WhatsApp, iMessage, Slack, and more to Claude AI.
"""
import asyncio
import logging
import signal

from claude_client.client import ClaudeGatewayClient
from config import Config
from session.manager import SessionManager
from utils.logging import setup_logging
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


async def cleanup_sessions_periodically(session_manager: SessionManager):
    """Run session cleanup every 24 hours."""
    while True:
        await asyncio.sleep(86400)
        session_manager.cleanup_expired()


async def main():
    setup_logging(level="INFO")
    Config.validate()

    session_manager = SessionManager(
        sessions_dir=f"{Config.DATA_DIR}/sessions",
        ttl_days=Config.SESSION_TTL_DAYS,
        max_tokens=Config.MAX_HISTORY_TOKENS,
    )

    claude_client = ClaudeGatewayClient(
        api_key=Config.AI_API_KEY,
        model=Config.AI_MODEL,
        base_url=Config.AI_BASE_URL,
        max_tool_iterations=Config.MAX_TOOL_ITERATIONS,
        workspace_dir=Config.WORKSPACE_DIR,
        data_dir=Config.DATA_DIR,
    )

    rate_limiter = RateLimiter(max_calls=20, period_seconds=60)

    bots = []
    tasks = []

    if Config.TELEGRAM_ENABLED:
        from platforms.telegram_bot import TelegramBot
        bots.append(TelegramBot(session_manager, claude_client, rate_limiter, Config))

    if Config.DISCORD_ENABLED:
        from platforms.discord_bot import DiscordBot
        bots.append(DiscordBot(session_manager, claude_client, rate_limiter, Config))

    if Config.WHATSAPP_ENABLED:
        from platforms.whatsapp_bot import WhatsAppBot
        bots.append(WhatsAppBot(session_manager, claude_client, rate_limiter, Config))

    if Config.IMESSAGE_ENABLED:
        from platforms.imessage_bot import IMessageBot
        bots.append(IMessageBot(session_manager, claude_client, rate_limiter, Config))

    if Config.SLACK_ENABLED:
        from platforms.slack_bot import SlackBot
        bots.append(SlackBot(session_manager, claude_client, rate_limiter, Config))

    if Config.WEBHOOK_ENABLED:
        from platforms.webhook_server import WebhookServer
        bots.append(WebhookServer(session_manager, claude_client, rate_limiter, Config))

    if Config.IDE_ENABLED:
        from platforms.ide_server import IDEServer
        bots.append(IDEServer(session_manager, claude_client, rate_limiter, Config))

    if not bots:
        logger.error("No platforms enabled. Check your .env configuration.")
        return

    logger.info("Mr. Crab starting with %d platform(s)...", len(bots))

    # Graceful shutdown handler
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _shutdown_signal():
        logger.info("Shutdown signal received.")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown_signal)
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler for all signals

    # Start all bots + session cleanup
    tasks = [asyncio.create_task(bot.start()) for bot in bots]
    tasks.append(asyncio.create_task(cleanup_sessions_periodically(session_manager)))

    # Wait for shutdown signal
    await shutdown_event.wait()

    logger.info("Shutting down Mr. Crab...")
    for bot in bots:
        try:
            await bot.stop()
        except Exception as e:
            logger.warning("Error stopping bot: %s", e)

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Mr. Crab stopped.")


if __name__ == "__main__":
    asyncio.run(main())
