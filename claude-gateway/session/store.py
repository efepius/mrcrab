import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self, sessions_dir: str):
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)

    def _path(self, session_id: str) -> str:
        safe_id = session_id.replace(":", "_").replace("/", "_")
        return os.path.join(self.sessions_dir, f"{safe_id}.json")

    def load(self, session_id: str) -> dict | None:
        path = self._path(session_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load session %s: %s", session_id, e)
            return None

    def save(self, session_id: str, data: dict):
        path = self._path(session_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error("Failed to save session %s: %s", session_id, e)

    def delete(self, session_id: str):
        path = self._path(session_id)
        if os.path.exists(path):
            os.remove(path)

    def list_all(self) -> list[dict]:
        sessions = []
        for filename in os.listdir(self.sessions_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.sessions_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    sessions.append(json.load(f))
            except Exception:
                pass
        return sessions

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
