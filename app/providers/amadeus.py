"""Amadeus 航班 Provider。

该适配器把 Amadeus Flight Offers Search 的 OAuth2 + JSON 响应转换成项目
统一的 ``TransportOption``。默认使用 test 环境，避免把测试联调误认为真实
出票；真正的 Client ID 和 Client Secret 由使用者在 Amadeus 开发者平台创建。
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any

import httpx

from app.schemas import TransportOption, TripRequest


class AmadeusProviderError(RuntimeError):
    """Amadeus 鉴权、查询或响应转换失败。"""


# 先覆盖项目演示中常用的中文城市；也支持用户直接输入三字母机场代码。
CITY_TO_IATA = {
    "北京": "PEK",
    "北京市": "PEK",
    "上海": "SHA",
    "上海市": "SHA",
    "广州": "CAN",
    "广州市": "CAN",
    "深圳": "SZX",
    "深圳市": "SZX",
    "太原": "TYN",
    "太原市": "TYN",
    "成都": "CTU",
    "成都市": "CTU",
    "西安": "XIY",
    "西安市": "XIY",
    "杭州": "HGH",
    "杭州市": "HGH",
    "南京": "NKG",
    "南京市": "NKG",
    "武汉": "WUH",
    "武汉市": "WUH",
    "重庆": "CKG",
    "重庆市": "CKG",
}


def _location_code(location: str) -> str:
    value = location.strip()
    if re.fullmatch(r"[A-Za-z]{3}", value):
        return value.upper()
    code = CITY_TO_IATA.get(value) or CITY_TO_IATA.get(value.removesuffix("市"))
    if code:
        return code
    raise AmadeusProviderError(
        f"暂不支持将地点“{location}”转换为机场代码，请输入三字母 IATA 代码，"
        "例如 PEK、TYN，或在 app/providers/amadeus.py 中补充城市映射。"
    )


def _duration_minutes(value: str | None) -> int | None:
    """解析 Amadeus 的 ISO 8601 时长，例如 PT2H35M。"""
    if not value:
        return None
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", value)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


def _api_error(response: httpx.Response, provider_name: str) -> AmadeusProviderError:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    errors = payload.get("errors") if isinstance(payload, dict) else None
    detail = ""
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            detail = str(first.get("detail") or first.get("title") or "")
    if not detail and isinstance(payload, dict):
        detail = str(payload.get("error_description") or payload.get("error") or "")
    detail = detail or response.text[:200] or "无详细错误信息"
    return AmadeusProviderError(
        f"{provider_name} 返回 HTTP {response.status_code}：{detail}"
    )


class AmadeusFlightProvider:
    """调用 Amadeus Flight Offers Search 的真实航班 Provider。"""

    name = "amadeus_flight"
    transport_type = "flight"
    mode = "amadeus-test"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        base_url: str = "https://test.api.amadeus.com",
        timeout_seconds: float = 8.0,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("Amadeus Client ID 和 Client Secret 不能为空")
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    async def search(self, request: TripRequest) -> list[TransportOption]:
        params: dict[str, Any] = {
            "originLocationCode": _location_code(request.origin),
            "destinationLocationCode": _location_code(request.destination),
            "departureDate": request.travel_date.isoformat(),
            "adults": 1,
            "currencyCode": "CNY",
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            token = await self._get_access_token(client)
            response = await client.get(
                f"{self.base_url}/v2/shopping/flight-offers",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 401:
                # token 失效时只刷新一次，避免与外层 ReliableProvider 重试叠加失控。
                self._access_token = None
                token = await self._get_access_token(client)
                response = await client.get(
                    f"{self.base_url}/v2/shopping/flight-offers",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
            if response.is_error:
                raise _api_error(response, self.name)
            try:
                payload = response.json()
            except ValueError as exc:
                raise AmadeusProviderError("Amadeus 返回的不是 JSON") from exc

        return self.map_response(payload, request)

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        if self._access_token and time.monotonic() < self._token_expires_at:
            return self._access_token
        response = await client.post(
            f"{self.base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.is_error:
            raise _api_error(response, self.name)
        try:
            payload = response.json()
            token = str(payload["access_token"])
            expires_in = int(payload.get("expires_in", 1800))
        except (KeyError, TypeError, ValueError) as exc:
            raise AmadeusProviderError("Amadeus 鉴权响应缺少 access_token") from exc
        self._access_token = token
        # 提前 30 秒刷新，避免恰好在请求过程中失效。
        self._token_expires_at = time.monotonic() + max(expires_in - 30, 1)
        return token

    def map_response(
        self, payload: Any, request: TripRequest
    ) -> list[TransportOption]:
        """把 Amadeus 响应转换成内部统一格式，单元测试也可直接调用。"""
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise AmadeusProviderError("Amadeus 响应缺少 data 航班列表")

        options: list[TransportOption] = []
        for offer in rows:
            if not isinstance(offer, dict):
                continue
            itineraries = offer.get("itineraries") or []
            if not itineraries or not isinstance(itineraries[0], dict):
                continue
            itinerary = itineraries[0]
            segments = itinerary.get("segments") or []
            if not segments or not isinstance(segments[0], dict):
                continue
            first_segment = segments[0]
            last_segment = segments[-1]
            departure = first_segment.get("departure", {}).get("at")
            arrival = last_segment.get("arrival", {}).get("at")
            if not departure or not arrival:
                continue
            try:
                departure_time = datetime.fromisoformat(str(departure).replace("Z", "+00:00"))
                arrival_time = datetime.fromisoformat(str(arrival).replace("Z", "+00:00"))
            except ValueError as exc:
                raise AmadeusProviderError("Amadeus 航班时间格式无法解析") from exc

            price_data = offer.get("price") or {}
            raw_price = price_data.get("grandTotal") or price_data.get("total")
            try:
                price = float(raw_price)
            except (TypeError, ValueError) as exc:
                raise AmadeusProviderError("Amadeus 航班价格格式无法解析") from exc

            duration = _duration_minutes(itinerary.get("duration"))
            if duration is None:
                duration = max(1, int((arrival_time - departure_time).total_seconds() / 60))
            fare_details = (offer.get("travelerPricings") or [{}])[0]
            fare_segments = fare_details.get("fareDetailsBySegment") or []
            cabin = fare_segments[0].get("cabin") if fare_segments else None
            bookable = offer.get("numberOfBookableSeats")
            ticket_count = int(bookable) if bookable is not None else None
            options.append(
                TransportOption(
                    provider=self.name,
                    transport_type="flight",
                    origin=request.origin,
                    destination=request.destination,
                    departure_time=departure_time,
                    arrival_time=arrival_time,
                    price=price,
                    duration_minutes=duration,
                    transfers=max(0, len(segments) - 1),
                    ticket_count=ticket_count,
                    seat_type=str(cabin) if cabin else None,
                    is_available=ticket_count is None or ticket_count > 0,
                    booking_url=None,
                )
            )
        return options
