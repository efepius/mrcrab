import io
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from media.handler import bytes_to_vision_block
from .base import BasePlatformBot

logger = logging.getLogger(__name__)

PLATFORM = "telegram"


class TelegramBot(BasePlatformBot):
    def __init__(self, session_manager, claude_client, rate_limiter, config):
        super().__init__(session_manager, claude_client, rate_limiter, config)
        self.app = (
            Application.builder()
            .token(config.TELEGRAM_BOT_TOKEN)
            .build()
        )
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("reset", self._cmd_reset))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("voice", self._cmd_voice_toggle))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text)
        )
        self.app.add_handler(
            MessageHandler(filters.PHOTO | filters.Document.IMAGE, self._on_media)
        )

    async def start(self):
        logger.info("Starting Telegram bot (polling)...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot running.")

    async def stop(self):
        logger.info("Stopping Telegram bot...")
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()

    # --- Command handlers ---

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Hi! I'm Mr. Crab, your personal Claude AI assistant.\n"
            "Just send me a message to get started.\n\n"
            "Commands:\n"
            "/reset — clear conversation history\n"
            "/voice — toggle voice replies\n"
            "/help — show this message"
        )

    async def _cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.sessions.reset(PLATFORM, str(user.id))
        await update.message.reply_text("Session reset. Starting fresh.")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        voice_status = "on" if context.user_data.get("voice_mode") else "off"
        await update.message.reply_text(
            "I'm Mr. Crab, your Claude AI assistant.\n\n"
            "I can:\n"
            "• Answer questions and help with tasks\n"
            "• Run commands on the server\n"
            "• Read and write files\n"
            "• Fetch web content\n"
            "• Analyze images you send\n\n"
            "/reset — start a new conversation\n"
            f"/voice — toggle voice replies (currently {voice_status})\n"
            "/help — show this message"
        )

    async def _cmd_voice_toggle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.config.VOICE_ENABLED:
            await update.message.reply_text(
                "Voice is not enabled. Set ELEVENLABS_API_KEY in .env to enable it."
            )
            return
        current = context.user_data.get("voice_mode", False)
        context.user_data["voice_mode"] = not current
        state = "ON" if not current else "OFF"
        await update.message.reply_text(f"Voice replies turned {state}.")

    # --- Message handlers ---

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        text = update.message.text or ""

        await update.message.chat.send_action("typing")
        response = await self.handle_message(
            platform=PLATFORM,
            user_id=str(user.id),
            display_name=user.full_name or user.username or str(user.id),
            text=text,
        )

        # Send voice reply if voice mode is on
        if context.user_data.get("voice_mode") and self.config.VOICE_ENABLED:
            await self._send_voice(update, response)
        else:
            await update.message.reply_text(response)

    async def _send_voice(self, update: Update, text: str):
        from utils.voice import text_to_speech
        audio = await text_to_speech(
            text,
            api_key=self.config.ELEVENLABS_API_KEY,
            voice_id=self.config.ELEVENLABS_VOICE_ID,
        )
        if audio:
            await update.message.reply_voice(voice=io.BytesIO(audio))
        else:
            await update.message.reply_text(text)

    async def _on_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        caption = update.message.caption or "What is in this image?"

        # Get the largest photo or document
        media_block = None
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            data = await file.download_as_bytearray()
            media_block = await bytes_to_vision_block(bytes(data), "image/jpeg")
        elif update.message.document:
            doc = update.message.document
            if doc.mime_type and doc.mime_type.startswith("image/"):
                file = await context.bot.get_file(doc.file_id)
                data = await file.download_as_bytearray()
                media_block = await bytes_to_vision_block(bytes(data), doc.mime_type)

        await update.message.chat.send_action("typing")
        response = await self.handle_message(
            platform=PLATFORM,
            user_id=str(user.id),
            display_name=user.full_name or user.username or str(user.id),
            text=caption,
            media_blocks=[media_block] if media_block else None,
        )
        await update.message.reply_text(response)
