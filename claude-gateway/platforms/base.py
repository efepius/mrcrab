import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BasePlatformBot(ABC):
    def __init__(self, session_manager, claude_client, rate_limiter, config):
        self.sessions = session_manager
        self.claude = claude_client
        self.rate_limiter = rate_limiter
        self.config = config

    @abstractmethod
    async def start(self): ...

    @abstractmethod
    async def stop(self): ...

    async def handle_message(
        self,
        platform: str,
        user_id: str,
        display_name: str,
        text: str,
        media_blocks: list[dict] | None = None,
    ) -> str:
        """Shared message handling logic for all platforms."""
        user_key = f"{platform}:{user_id}"

        # Access control
        if self.config.ALLOWED_USER_IDS and user_id not in self.config.ALLOWED_USER_IDS:
            logger.warning("Blocked unauthorized user: %s", user_key)
            return "You are not authorized to use this bot."

        # Rate limit
        if not self.rate_limiter.is_allowed(user_key):
            wait = self.rate_limiter.seconds_until_allowed(user_key)
            return f"Slow down — you're sending too many messages. Try again in {int(wait)}s."

        # Handle /reset command
        if text.strip().lower() in ("/reset", "!reset"):
            self.sessions.reset(platform, user_id)
            return "Session reset. Starting fresh."

        # Load session
        session = self.sessions.get(platform, user_id)
        session["display_name"] = display_name

        # Trim history if needed
        self.sessions.trim_history(session)

        # Call Claude
        try:
            response_text, updated_history = await self.claude.chat(
                message=text,
                history=session["history"],
                media_blocks=media_blocks,
            )
        except Exception as e:
            logger.error("Claude chat error for %s: %s", user_key, e)
            return "Sorry, something went wrong. Please try again."

        session["history"] = updated_history
        self.sessions.save(session)

        # Truncate response if platform has a limit
        max_len = self.config.MAX_MESSAGE_LENGTH
        if len(response_text) > max_len:
            response_text = response_text[:max_len] + "\n\n[...response truncated]"

        return response_text
