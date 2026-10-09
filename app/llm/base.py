"""大模型客户端的最小抽象。"""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    async def chat(self, system_prompt: str, user_message: str) -> str:
        """根据系统提示词和用户输入返回文本结果。"""

