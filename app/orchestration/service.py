"""订票查询编排服务，供结构化和自然语言接口共同复用。"""

from __future__ import annotations

import asyncio

from app.providers.base import TransportProvider
from app.schemas import PlanResponse, TransportOption, TripRequest
from app.validation.hard_rules import filter_options


async def build_plan(
    request: TripRequest,
    providers: list[TransportProvider],
) -> PlanResponse:
    results = await asyncio.gather(
        *(provider.search(request) for provider in providers),
        return_exceptions=True,
    )
    options: list[TransportOption] = []
    errors: list[str] = []
    for provider, result in zip(providers, results, strict=True):
        if isinstance(result, Exception):
            errors.append(f"{provider.name}: {result}")
        else:
            options.extend(result)

    valid_options = filter_options(options, request)
    message = "找到符合条件的出行方案。" if valid_options else "没有找到符合条件的方案。"
    return PlanResponse(
        request=request,
        options=valid_options,
        total=len(valid_options),
        message=message,
        provider_errors=errors,
    )
