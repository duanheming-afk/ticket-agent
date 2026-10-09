"""将不同平台的 JSON 字段映射为统一交通方案。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas import TransportOption, TripRequest


class MappingError(RuntimeError):
    """外部 Provider 返回的数据无法映射。"""


DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "origin": ("origin", "from", "from_city", "departure_city"),
    "destination": ("destination", "to", "to_city", "arrival_city"),
    "departure_time": ("departure_time", "depart_at", "departure", "start_time"),
    "arrival_time": ("arrival_time", "arrive_at", "arrival", "end_time"),
    "price": ("price", "fare", "amount", "total_price"),
    "duration_minutes": ("duration_minutes", "duration", "minutes"),
    "transfers": ("transfers", "transfer_count", "stops"),
    "ticket_count": ("ticket_count", "remaining", "remaining_tickets", "available_count"),
    "seat_type": ("seat_type", "seat", "cabin", "class_name"),
    "is_available": ("is_available", "available", "bookable"),
    "booking_url": ("booking_url", "url", "link"),
}


def _read_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _first_value(row: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    for candidate in candidates:
        value = _read_path(row, candidate)
        if value is not None:
            return value
    return None


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        raise MappingError(f"缺少字段：{field_name}")
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise MappingError(f"字段 {field_name} 不是有效时间：{value}") from exc


class TransportOptionMapper:
    def __init__(
        self,
        *,
        items_path: str | None = None,
        field_map: dict[str, str | list[str]] | None = None,
    ) -> None:
        self.items_path = items_path
        self.field_map = field_map or {}

    def map_response(
        self,
        payload: Any,
        *,
        provider: str,
        transport_type: str,
        request: TripRequest,
    ) -> list[TransportOption]:
        rows = self._extract_rows(payload)
        options: list[TransportOption] = []
        for row in rows:
            if not isinstance(row, dict):
                raise MappingError(f"{provider} 的方案条目不是 JSON 对象")
            options.append(self._map_row(row, provider, transport_type))
        return [
            option
            for option in options
            if option.transport_type == transport_type
            and option.origin == request.origin
            and option.destination == request.destination
            and option.departure_time.date() == request.travel_date
        ]

    def _extract_rows(self, payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            raise MappingError("Provider 返回值必须是 JSON 数组或对象")
        if self.items_path:
            rows = _read_path(payload, self.items_path)
            if isinstance(rows, list):
                return rows
            raise MappingError(f"无法在返回结果中找到数组：{self.items_path}")
        for path in ("options", "data.items", "data", "results"):
            rows = _read_path(payload, path)
            if isinstance(rows, list):
                return rows
        return [payload]

    def _candidate_paths(self, field_name: str) -> tuple[str, ...]:
        custom = self.field_map.get(field_name)
        if isinstance(custom, str):
            return (custom,)
        if isinstance(custom, list):
            return tuple(custom)
        return DEFAULT_ALIASES[field_name]

    def _map_row(
        self,
        row: dict[str, Any],
        provider: str,
        transport_type: str,
    ) -> TransportOption:
        departure = _parse_datetime(
            _first_value(row, self._candidate_paths("departure_time")),
            "departure_time",
        )
        arrival = _parse_datetime(
            _first_value(row, self._candidate_paths("arrival_time")),
            "arrival_time",
        )
        duration_value = _first_value(row, self._candidate_paths("duration_minutes"))
        duration = int(float(duration_value)) if duration_value is not None else int(
            (arrival - departure).total_seconds() / 60
        )
        ticket_value = _first_value(row, self._candidate_paths("ticket_count"))
        ticket_count = int(ticket_value) if ticket_value is not None else None
        available_value = _first_value(row, self._candidate_paths("is_available"))
        is_available = (
            bool(available_value)
            if available_value is not None
            else ticket_count is None or ticket_count > 0
        )
        return TransportOption(
            provider=provider,
            transport_type=transport_type,
            origin=str(_first_value(row, self._candidate_paths("origin")) or ""),
            destination=str(_first_value(row, self._candidate_paths("destination")) or ""),
            departure_time=departure,
            arrival_time=arrival,
            price=float(_first_value(row, self._candidate_paths("price")) or 0),
            duration_minutes=duration,
            transfers=int(_first_value(row, self._candidate_paths("transfers")) or 0),
            ticket_count=ticket_count,
            seat_type=_first_value(row, self._candidate_paths("seat_type")),
            is_available=is_available,
            booking_url=_first_value(row, self._candidate_paths("booking_url")),
        )
