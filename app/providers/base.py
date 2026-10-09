"""交通数据 Provider 的统一接口。"""

from __future__ import annotations

from typing import Protocol

from app.schemas import TransportOption, TripRequest


class TransportProvider(Protocol):
    name: str
    transport_type: str

    async def search(self, request: TripRequest) -> list[TransportOption]:
        """根据统一需求查询并返回统一格式的交通方案。"""
