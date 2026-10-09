"""工具白名单和统一执行入口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.providers.base import TransportProvider
from app.schemas import TransportOption, TripRequest


class ToolNotFoundError(RuntimeError):
    """请求了未注册的工具。"""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    transport_type: str
    provider: TransportProvider


class ToolRegistry:
    """只允许 Agent 调用注册过的工具，避免动态执行任意函数。"""

    def __init__(self, specs: list[ToolSpec]) -> None:
        self._tools = {spec.name: spec for spec in specs}

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def has(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> ToolSpec:
        spec = self._tools.get(name)
        if spec is None:
            raise ToolNotFoundError(f"工具未注册：{name}")
        return spec

    def function_definitions(self) -> list[dict[str, Any]]:
        """转换为 Ollama 原生 Function Calling 的工具定义。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "origin": {"type": "string", "description": "出发地"},
                            "destination": {"type": "string", "description": "目的地"},
                            "travel_date": {"type": "string", "description": "出发日期，YYYY-MM-DD"},
                            "budget": {"type": "number", "description": "预算上限"},
                        },
                        "required": ["origin", "destination", "travel_date"],
                    },
                },
            }
            for spec in self._tools.values()
        ]

    async def execute(
        self, name: str, request: TripRequest
    ) -> list[TransportOption]:
        spec = self.get(name)
        return await spec.provider.search(request)
