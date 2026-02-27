import logging

import discord
from discord.ext import commands

from media.handler import bytes_to_vision_block
from .base import BasePlatformBot

logger = logging.getLogger(__name__)

PLATFORM = "discord"


class DiscordBot(BasePlatformBot):
    def __init__(self, session_manager, claude_client, rate_limiter, config):
        super().__init__(session_manager, claude_client, rate_limiter, config)

        intents = discord.Intents.default()
        intents.message_content = True

        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self._register_events()

    def _register_events(self):
        @self.bot.event
        async def on_ready():
            logger.info("Discord bot connected as %s", self.bot.user)

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author.bot:
                return

            # Only respond in DMs or when mentioned
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = self.bot.user in message.mentions

            if not is_dm and not is_mentioned:
                return

            # Strip mention from text
            text = message.content
            if self.bot.user:
                text = text.replace(f"<@{self.bot.user.id}>", "").strip()

            if not text and not message.attachments:
                return

            # Handle /reset or !reset
            if text.lower() in ("/reset", "!reset"):
                self.sessions.reset(PLATFORM, str(message.author.id))
                await message.reply("Session reset. Starting fresh.")
                return

            # Collect image attachments
            media_blocks = []
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    data = await attachment.read()
                    block = await bytes_to_vision_block(data, attachment.content_type)
                    if block:
                        media_blocks.append(block)

            async with message.channel.typing():
                response = await self.handle_message(
                    platform=PLATFORM,
                    user_id=str(message.author.id),
                    display_name=message.author.display_name,
                    text=text or "Please describe the attached image.",
                    media_blocks=media_blocks or None,
                )

            # Discord has a 2000 char limit per message
            if len(response) <= 2000:
                await message.reply(response)
            else:
                # Split into chunks
                for i in range(0, len(response), 1990):
                    chunk = response[i:i + 1990]
                    await message.channel.send(chunk)

        @self.bot.command(name="reset")
        async def reset_cmd(ctx):
            self.sessions.reset(PLATFORM, str(ctx.author.id))
            await ctx.reply("Session reset. Starting fresh.")

        @self.bot.command(name="help")
        async def help_cmd(ctx):
            await ctx.reply(
                "**Mr. Crab — Claude AI Assistant**\n\n"
                "I can answer questions, run server commands, fetch URLs, and analyze images.\n\n"
                "**Commands:**\n"
                "`!reset` — clear conversation history\n"
                "`!help` — show this message\n\n"
                "DM me or mention me in a server channel to chat."
            )

    async def start(self):
        logger.info("Starting Discord bot...")
        await self.bot.start(self.config.DISCORD_BOT_TOKEN)

    async def stop(self):
        logger.info("Stopping Discord bot...")
        await self.bot.close()
