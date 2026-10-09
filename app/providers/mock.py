"""第一阶段的本地 Mock Provider，后续可替换为真实 API 适配器。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.schemas import TransportOption, TripRequest


class MockProvider:
    def __init__(self, transport_type: str, data_path: str | Path) -> None:
        self.name = f"mock_{transport_type}"
        self.transport_type = transport_type
        self.data_path = Path(data_path)

    async def search(self, request: TripRequest) -> list[TransportOption]:
        """模拟异步查询，验证统一 Provider 接口和后续并发编排。"""
        await asyncio.sleep(0)
        rows = json.loads(self.data_path.read_text(encoding="utf-8"))
        options = [TransportOption.model_validate(row) for row in rows]
        return [
            option
            for option in options
            if option.transport_type in request.transport_types
            and option.origin == request.origin
            and option.destination == request.destination
            and option.departure_time.date() == request.travel_date
        ]
