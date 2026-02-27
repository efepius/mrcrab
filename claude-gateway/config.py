import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # === AI Provider (OpenAI-compatible) ===
    # Default: Ollama (local, free, no API key needed)
    # Run scripts/install-ollama.sh on your VM to set up automatically
    AI_API_KEY = os.getenv("AI_API_KEY", "ollama")
    AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:11434/v1")
    AI_MODEL = os.getenv("AI_MODEL", "llama3.2-vision:11b")

    # === Platforms ===

    # Telegram: get token from @BotFather
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN)

    # Discord: https://discord.com/developers/applications
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
    DISCORD_ENABLED = bool(DISCORD_BOT_TOKEN)

    # WhatsApp: requires Go 1.21+ on the VM
    WHATSAPP_SESSION_FILE = os.getenv("WHATSAPP_SESSION_FILE", "")
    WHATSAPP_ENABLED = bool(WHATSAPP_SESSION_FILE)

    # iMessage (BlueBubbles bridge — requires a Mac)
    BLUEBUBBLES_URL = os.getenv("BLUEBUBBLES_URL", "")
    BLUEBUBBLES_PASSWORD = os.getenv("BLUEBUBBLES_PASSWORD", "")
    IMESSAGE_ENABLED = bool(BLUEBUBBLES_URL)

    # Slack (Socket Mode)
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
    SLACK_ENABLED = bool(SLACK_BOT_TOKEN and SLACK_APP_TOKEN)

    # Webhook HTTP server
    WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")
    WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8787"))
    WEBHOOK_ENABLED = os.getenv("WEBHOOK_ENABLED", "false").lower() == "true"

    # === Voice TTS (ElevenLabs — optional) ===
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    VOICE_ENABLED = bool(os.getenv("ELEVENLABS_API_KEY", ""))

    # === Access control ===
    ALLOWED_USER_IDS: set = set(
        uid.strip()
        for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
        if uid.strip()
    )

    # === Tool settings ===
    MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "10"))
    WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "/opt/mrcrab/data/workspace")
    DATA_DIR = os.getenv("DATA_DIR", "/opt/mrcrab/data")

    # === Session settings ===
    SESSION_TTL_DAYS = int(os.getenv("SESSION_TTL_DAYS", "30"))
    MAX_HISTORY_TOKENS = int(os.getenv("MAX_HISTORY_TOKENS", "100000"))

    # === Message settings ===
    MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "4000"))

    @classmethod
    def validate(cls):
        if not cls.AI_API_KEY:
            raise ValueError(
                "AI_API_KEY is required in .env\n"
                "Get a free key at: https://build.nvidia.com\n"
                "Or use Kimi: https://platform.moonshot.cn"
            )

        enabled = [
            name for name, flag in [
                ("Telegram", cls.TELEGRAM_ENABLED),
                ("Discord", cls.DISCORD_ENABLED),
                ("WhatsApp", cls.WHATSAPP_ENABLED),
                ("iMessage", cls.IMESSAGE_ENABLED),
                ("Slack", cls.SLACK_ENABLED),
                ("Webhook", cls.WEBHOOK_ENABLED),
            ] if flag
        ]

        if not enabled:
            raise ValueError(
                "No platform tokens configured. Set at least one of:\n"
                "TELEGRAM_BOT_TOKEN, DISCORD_BOT_TOKEN, WHATSAPP_SESSION_FILE,\n"
                "BLUEBUBBLES_URL, SLACK_BOT_TOKEN+SLACK_APP_TOKEN, WEBHOOK_ENABLED=true"
            )

        print(f"[Mr. Crab] AI provider: {cls.AI_BASE_URL}")
        print(f"[Mr. Crab] Model: {cls.AI_MODEL}")
        print(f"[Mr. Crab] Platforms: {', '.join(enabled)}")
