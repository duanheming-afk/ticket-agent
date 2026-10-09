"""简单的内存会话存储，用于 MVP 多轮对话。"""

from __future__ import annotations

from uuid import uuid4

from app.schemas import ParsedTripRequest


class ConversationStore:
    """保存每个会话最近一次的结构化出行条件。"""

    def __init__(self) -> None:
        self._sessions: dict[str, ParsedTripRequest] = {}

    def new_session_id(self) -> str:
        return uuid4().hex[:12]

    def get(self, session_id: str) -> ParsedTripRequest | None:
        return self._sessions.get(session_id)

    def save(self, session_id: str, parsed: ParsedTripRequest) -> None:
        self._sessions[session_id] = parsed

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
