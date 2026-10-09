"""通用 HTTP JSON 交通 Provider。

真实平台的字段通常不同，因此本适配器要求对方返回统一的 TransportOption
字段，后续可以为具体平台继承该类实现字段映射。
"""

from __future__ import annotations

from typing import Any

import httpx

from app.schemas import TransportOption, TripRequest
from app.providers.mapper import TransportOptionMapper


class HttpJsonProvider:
    def __init__(
        self,
        transport_type: str,
        endpoint: str,
        *,
        name: str | None = None,
        headers: dict[str, str] | None = None,
        mapper: TransportOptionMapper | None = None,
    ) -> None:
        self.transport_type = transport_type
        self.endpoint = endpoint
        self.name = name or f"http_{transport_type}"
        self.headers = headers or {}
        self.mapper = mapper or TransportOptionMapper()

    async def search(self, request: TripRequest) -> list[TransportOption]:
        params: dict[str, Any] = {
            "origin": request.origin,
            "destination": request.destination,
            "travel_date": request.travel_date.isoformat(),
            "transport_type": self.transport_type,
        }
        if request.depart_after is not None:
            params["depart_after"] = request.depart_after.strftime("%H:%M")
        if request.budget is not None:
            params["budget"] = request.budget

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.endpoint,
                params=params,
                headers=self.headers,
            )
            response.raise_for_status()

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"{self.name} 返回的不是 JSON") from exc

        return self.mapper.map_response(
            payload,
            provider=self.name,
            transport_type=self.transport_type,
            request=request,
        )
