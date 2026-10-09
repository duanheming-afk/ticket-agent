from datetime import date

import pytest

from app.providers.reliable import CircuitOpenError, ProviderCallError, ReliableProvider
from app.schemas import TripRequest


class FlakyProvider:
    name = "flaky_train"
    transport_type = "train"

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    async def search(self, request: TripRequest):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("临时网络错误")
        return []


def request() -> TripRequest:
    return TripRequest(
        origin="太原",
        destination="北京",
        travel_date=date(2026, 9, 20),
        transport_types=["train"],
    )


@pytest.mark.asyncio
async def test_reliable_provider_retries_then_recovers() -> None:
    provider = FlakyProvider(failures=1)
    reliable = ReliableProvider(
        provider,
        max_retries=2,
        retry_backoff_seconds=0,
    )

    assert await reliable.search(request()) == []
    assert provider.calls == 2
    assert reliable.status()["retry_count"] == 1
    assert reliable.status()["success_calls"] == 1


@pytest.mark.asyncio
async def test_reliable_provider_opens_circuit_after_failures() -> None:
    provider = FlakyProvider(failures=10)
    reliable = ReliableProvider(
        provider,
        max_retries=0,
        failure_threshold=1,
        cooldown_seconds=60,
    )

    with pytest.raises(ProviderCallError):
        await reliable.search(request())
    with pytest.raises(CircuitOpenError):
        await reliable.search(request())
    assert provider.calls == 1
    assert reliable.status()["circuit_state"] == "open"
