import json
import logging
from datetime import datetime, timedelta, timezone

from .store import SessionStore

logger = logging.getLogger(__name__)


def _estimate_tokens(history: list[dict]) -> int:
    """Rough token estimate: 4 chars ≈ 1 token (works for any provider)."""
    return len(json.dumps(history)) // 4


class SessionManager:
    def __init__(self, sessions_dir: str, ttl_days: int = 30, max_tokens: int = 100_000):
        self.store = SessionStore(sessions_dir)
        self.ttl_days = ttl_days
        self.max_tokens = max_tokens
        self._cache: dict[str, dict] = {}

    def _session_id(self, platform: str, user_id: str) -> str:
        return f"{platform}:{user_id}"

    def get(self, platform: str, user_id: str) -> dict:
        sid = self._session_id(platform, user_id)

        if sid in self._cache:
            return self._cache[sid]

        data = self.store.load(sid)
        if data is None:
            data = {
                "session_id": sid,
                "platform": platform,
                "user_id": user_id,
                "display_name": "",
                "created_at": self.store.now_iso(),
                "last_active": self.store.now_iso(),
                "message_count": 0,
                "history": [],
            }

        self._cache[sid] = data
        return data

    def save(self, session: dict):
        session["last_active"] = self.store.now_iso()
        session["message_count"] = session.get("message_count", 0) + 1
        self._cache[session["session_id"]] = session
        self.store.save(session["session_id"], session)

    def reset(self, platform: str, user_id: str):
        sid = self._session_id(platform, user_id)
        if sid in self._cache:
            self._cache[sid]["history"] = []
            self._cache[sid]["message_count"] = 0
            self.store.save(sid, self._cache[sid])
        else:
            self.store.delete(sid)
        logger.info("Session reset: %s", sid)

    def trim_history(self, session: dict) -> list[dict]:
        """
        Trim history with a sliding window to stay under max_tokens.
        Removes oldest user+assistant pairs from the front.
        """
        history = session.get("history", [])
        if not history:
            return history

        token_count = _estimate_tokens(history)

        while token_count > self.max_tokens and len(history) >= 2:
            history = history[2:]
            token_count = _estimate_tokens(history)

        session["history"] = history
        return history

    def cleanup_expired(self):
        """Remove sessions older than TTL. Call this once daily."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ttl_days)
        removed = 0
        for session in self.store.list_all():
            try:
                last = datetime.fromisoformat(session.get("last_active", ""))
                if last < cutoff:
                    sid = session["session_id"]
                    self.store.delete(sid)
                    self._cache.pop(sid, None)
                    removed += 1
            except Exception:
                pass
        if removed:
            logger.info("Cleaned up %d expired sessions", removed)
