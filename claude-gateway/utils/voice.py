"""
Voice TTS via ElevenLabs API.
Set ELEVENLABS_API_KEY in .env to enable voice responses.
Voice replies are sent as audio files on platforms that support it (e.g. Telegram).
"""
import logging
import os

import aiohttp

logger = logging.getLogger(__name__)

ELEVENLABS_API = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — clear, neutral voice


async def text_to_speech(text: str, api_key: str, voice_id: str = DEFAULT_VOICE_ID) -> bytes | None:
    """Convert text to MP3 audio bytes using ElevenLabs."""
    if not api_key:
        return None

    # Trim to ElevenLabs free tier limit (2500 chars)
    if len(text) > 2500:
        text = text[:2500] + "..."

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ELEVENLABS_API}/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    logger.warning("ElevenLabs TTS failed: HTTP %s", resp.status)
                    return None
                return await resp.read()
    except Exception as e:
        logger.warning("ElevenLabs TTS error: %s", e)
        return None
