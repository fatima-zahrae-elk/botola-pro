# chatbot-service/src/memory.py
import json
import time
from typing import List, Dict, Optional
from collections import defaultdict

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .config import CONVERSATION_TURNS, SESSION_TIMEOUT, REDIS_URL


class ConversationMemory:
    """
    Manages conversation history per session.
    Falls back to in-memory dict if Redis unavailable or fails mid-session.
    """

    def __init__(self, redis_url: str = None):
        self.redis = None
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis = redis.from_url(redis_url, decode_responses=True)
                self.redis.ping()
                print("[OK] Redis connected for conversation memory")
            except Exception as e:
                print(f"[WARN] Redis unavailable, using in-memory: {e}")
                self.redis = None

        self.local_store = defaultdict(list)

    def add_turn(self, session_id: str, role: str, content: str,
                 metadata: Dict = None):
        """Add a conversation turn."""
        turn = {
            "role": role,  # user | assistant | system
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }

        if self.redis:
            try:
                key = f"chat:session:{session_id}"
                self.redis.lpush(key, json.dumps(turn))
                self.redis.ltrim(key, 0, CONVERSATION_TURNS * 2 - 1)
                self.redis.expire(key, SESSION_TIMEOUT)
                return
            except Exception:
                self.redis = None  # disable Redis, fall through to local

        # Fallback: in-memory
        self.local_store[session_id].append(turn)
        self.local_store[session_id] = self.local_store[session_id][-CONVERSATION_TURNS * 2:]

    def get_history(self, session_id: str) -> List[Dict]:
        """Get conversation history for a session."""
        if self.redis:
            try:
                key = f"chat:session:{session_id}"
                turns = self.redis.lrange(key, 0, -1)
                return [json.loads(t) for t in reversed(turns)]
            except Exception:
                self.redis = None  # disable Redis, fall through to local

        return self.local_store.get(session_id, [])

    def get_formatted_history(self, session_id: str,
                              max_turns: int = CONVERSATION_TURNS) -> str:
        """Get history formatted for LLM prompt."""
        history = self.get_history(session_id)
        recent = history[-max_turns * 2:] if len(history) > max_turns * 2 else history

        lines = []
        for turn in recent:
            role_label = "User" if turn["role"] == "user" else "Assistant"
            lines.append(f"{role_label}: {turn['content']}")

        return "\n".join(lines) if lines else "No previous conversation."

    def clear(self, session_id: str):
        """Clear session memory."""
        if self.redis:
            try:
                self.redis.delete(f"chat:session:{session_id}")
                return
            except Exception:
                self.redis = None
        self.local_store.pop(session_id, None)