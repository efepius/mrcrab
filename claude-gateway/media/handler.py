import base64
import logging
import os
import tempfile

import aiohttp
from PIL import Image

logger = logging.getLogger(__name__)

# Claude vision supported MIME types
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
MAX_IMAGE_DIMENSION = 2048


async def url_to_vision_block(url: str) -> dict | None:
    """Download a media URL and return a Claude vision content block."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return None
                content_type = resp.content_type or "image/jpeg"
                data = await resp.read()
    except Exception as e:
        logger.warning("Failed to download media from %s: %s", url, e)
        return None

    return _encode_image(data, content_type)


async def bytes_to_vision_block(data: bytes, content_type: str = "image/jpeg") -> dict | None:
    """Encode raw bytes as a Claude vision content block."""
    return _encode_image(data, content_type)


def _encode_image(data: bytes, content_type: str) -> dict | None:
    """Resize if needed and base64-encode image for Claude vision."""
    if len(data) > MAX_IMAGE_SIZE_BYTES:
        data = _resize_image(data)
        if data is None:
            return None

    # Normalise content type
    mime = content_type.split(";")[0].strip().lower()
    if mime not in SUPPORTED_IMAGE_TYPES:
        mime = "image/jpeg"

    encoded = base64.standard_b64encode(data).decode("utf-8")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": mime,
            "data": encoded,
        },
    }


def _resize_image(data: bytes) -> bytes | None:
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        img = Image.open(tmp_path)
        img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)

        out_path = tmp_path + "_resized.jpg"
        img.save(out_path, "JPEG", quality=85)
        with open(out_path, "rb") as f:
            result = f.read()

        os.unlink(tmp_path)
        os.unlink(out_path)
        return result
    except Exception as e:
        logger.warning("Image resize failed: %s", e)
        return None
