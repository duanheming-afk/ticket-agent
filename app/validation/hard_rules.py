"""第一阶段的确定性过滤规则。"""

from __future__ import annotations

from app.schemas import TransportOption, TripRequest


def filter_options(
    options: list[TransportOption], request: TripRequest
) -> list[TransportOption]:
    """过滤预算、出发时间和中转约束，不让 LLM 参与数字判断。"""
    valid: list[TransportOption] = []
    for option in options:
        if not option.is_available:
            continue
        if request.budget is not None and option.price > request.budget:
            continue
        if request.depart_after and option.departure_time.time() < request.depart_after:
            continue
        if not request.allow_transfer and option.transfers > 0:
            continue
        if option.transfers > request.max_transfers:
            continue
        if option.arrival_time <= option.departure_time:
            continue
        valid.append(option)
    return sorted(valid, key=lambda item: (item.price, item.duration_minutes, item.transfers))
