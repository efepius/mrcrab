"""
WhatsApp adapter using neonize (Python bindings for go-whatsapp / whatsmeow).

Setup on Ubuntu VM:
    sudo apt install golang-go   # or install Go 1.21+ manually
    pip install neonize

First run: a QR code is printed to stdout. Scan it with your phone
(WhatsApp > Linked Devices > Link a Device). Session is then saved to
WHATSAPP_SESSION_FILE and used automatically on subsequent starts.
"""
import logging

from media.handler import bytes_to_vision_block
from .base import BasePlatformBot

logger = logging.getLogger(__name__)

PLATFORM = "whatsapp"


class WhatsAppBot(BasePlatformBot):
    def __init__(self, session_manager, claude_client, rate_limiter, config):
        super().__init__(session_manager, claude_client, rate_limiter, config)
        self._client = None

    async def start(self):
        try:
            from neonize.client import NewClient
            from neonize.events import (
                ConnectedEv,
                MessageEv,
                QRChangedEv,
            )
            from neonize.proto.Neonize_pb2 import Message as NeonizeMessage
        except ImportError:
            logger.error(
                "neonize is not installed. Run: pip install neonize\n"
                "Also ensure Go 1.21+ is installed: sudo apt install golang-go"
            )
            return

        session_file = self.config.WHATSAPP_SESSION_FILE
        client = NewClient(session_file)
        self._client = client

        @client.event(QRChangedEv)
        def on_qr(_, qr: QRChangedEv):
            print("\n=== WhatsApp QR Code ===")
            print(f"Scan this with your phone: {qr.code}")
            print("=======================\n")

        @client.event(ConnectedEv)
        def on_connected(_, __):
            logger.info("WhatsApp connected successfully.")

        @client.event(MessageEv)
        def on_message(_, msg: MessageEv):
            import asyncio
            asyncio.create_task(self._handle_wa_message(msg))

        logger.info("Starting WhatsApp client (session: %s)...", session_file)
        client.connect()

    async def stop(self):
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass

    async def _handle_wa_message(self, msg):
        try:
            # Skip messages sent by us
            if msg.Info.MessageSource.IsFromMe:
                return

            chat_jid = msg.Info.MessageSource.Chat
            sender_jid = msg.Info.MessageSource.Sender
            user_id = str(sender_jid)

            # Extract text
            text = ""
            media_blocks = None

            if msg.Message.conversation:
                text = msg.Message.conversation
            elif msg.Message.extendedTextMessage.text:
                text = msg.Message.extendedTextMessage.text
            elif msg.Message.imageMessage.caption:
                text = msg.Message.imageMessage.caption or "What is in this image?"
                # Download image
                try:
                    data = await self._client.download_media_message(msg.Message)
                    block = await bytes_to_vision_block(data, "image/jpeg")
                    if block:
                        media_blocks = [block]
                except Exception as e:
                    logger.warning("Failed to download WA image: %s", e)

            if not text and not media_blocks:
                return

            response = await self.handle_message(
                platform=PLATFORM,
                user_id=user_id,
                display_name=user_id.split("@")[0],
                text=text or "Please describe the attached image.",
                media_blocks=media_blocks,
            )

            self._client.send_message(chat_jid, response)

        except Exception as e:
            logger.error("WhatsApp message handling error: %s", e)
