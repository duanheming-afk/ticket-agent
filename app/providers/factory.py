"""Provider 工厂：配置真实 URL 时使用 HTTP Provider，否则使用 Mock。"""

from __future__ import annotations

import os
from pathlib import Path

from app.providers.amadeus import AmadeusFlightProvider
from app.providers.http_json import HttpJsonProvider
from app.providers.mapper import TransportOptionMapper
from app.providers.mock import MockProvider
from app.providers.reliable import ReliableProvider


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def create_provider(transport_type: str, mock_path: str | Path) -> ReliableProvider:
    if transport_type == "flight" and os.getenv("AMADEUS_ENABLED", "false").lower() == "true":
        client_id = os.getenv("AMADEUS_CLIENT_ID", "").strip()
        client_secret = os.getenv("AMADEUS_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            raise ValueError(
                "AMADEUS_ENABLED=true 时必须配置 AMADEUS_CLIENT_ID 和 "
                "AMADEUS_CLIENT_SECRET"
            )
        base_provider = AmadeusFlightProvider(
            client_id,
            client_secret,
            base_url=os.getenv(
                "AMADEUS_BASE_URL", "https://test.api.amadeus.com"
            ).strip(),
            timeout_seconds=_env_float("PROVIDER_TIMEOUT_SECONDS", 8.0),
        )
    else:
        endpoint = os.getenv(f"{transport_type.upper()}_PROVIDER_URL", "").strip()
        if endpoint:
            prefix = transport_type.upper()
            api_key = os.getenv(f"{prefix}_PROVIDER_API_KEY", "").strip()
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            items_path = os.getenv(f"{prefix}_PROVIDER_ITEMS_PATH", "").strip() or None
            base_provider = HttpJsonProvider(
                transport_type,
                endpoint,
                headers=headers,
                mapper=TransportOptionMapper(items_path=items_path),
            )
        else:
            base_provider = MockProvider(transport_type, mock_path)

    return ReliableProvider(
        base_provider,
        timeout_seconds=_env_float("PROVIDER_TIMEOUT_SECONDS", 8.0),
        max_retries=_env_int("PROVIDER_MAX_RETRIES", 2),
        failure_threshold=_env_int("PROVIDER_FAILURE_THRESHOLD", 3),
        cooldown_seconds=_env_float("PROVIDER_COOLDOWN_SECONDS", 30.0),
    )
