from datetime import date, datetime

import pytest

from app.agent.tool_agent import ToolCallingAgent
from app.schemas import TransportOption, TripRequest
from app.tools.transport import create_transport_registry


class FakeProvider:
    def __init__(self, transport_type: str, options: list[TransportOption]) -> None:
        self.name = f"fake_{transport_type}"
        self.transport_type = transport_type
        self.options = options
        self.called = False

    async def search(self, request: TripRequest) -> list[TransportOption]:
        self.called = True
        return self.options


@pytest.mark.asyncio
async def test_agent_only_calls_requested_transport_tools() -> None:
    train = FakeProvider(
        "train",
        [
            TransportOption(
                provider="fake_train",
                transport_type="train",
                origin="太原",
                destination="北京",
                departure_time=datetime(2026, 9, 20, 8, 30),
                arrival_time=datetime(2026, 9, 20, 11, 45),
                price=267,
                duration_minutes=195,
                transfers=0,
            )
        ],
    )
    flight = FakeProvider("flight", [])
    agent = ToolCallingAgent(create_transport_registry([train, flight]))
    request = TripRequest(
        origin="太原",
        destination="北京",
        travel_date=date(2026, 9, 20),
        transport_types=["train"],
        budget=500,
    )

    result = await agent.run(request)

    assert train.called is True
    assert flight.called is False
    assert [call.name for call in result.tool_calls] == ["search_train"]
    assert result.tool_calls[0].status == "success"
    assert result.total == 1
