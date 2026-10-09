from datetime import date, time

from app.schemas import TransportOption, TripRequest
from app.validation.hard_rules import filter_options


def test_filter_by_budget_and_departure_time() -> None:
    request = TripRequest(
        origin="太原",
        destination="北京",
        travel_date=date(2026, 9, 20),
        depart_after=time(8, 0),
        budget=500,
        transport_types=["train", "flight"],
        allow_transfer=False,
        max_transfers=0,
    )
    options = [
        TransportOption(
            provider="test",
            transport_type="train",
            origin="太原",
            destination="北京",
            departure_time="2026-09-20T07:30:00",
            arrival_time="2026-09-20T10:30:00",
            price=200,
            duration_minutes=180,
        ),
        TransportOption(
            provider="test",
            transport_type="train",
            origin="太原",
            destination="北京",
            departure_time="2026-09-20T08:30:00",
            arrival_time="2026-09-20T11:30:00",
            price=300,
            duration_minutes=180,
        ),
    ]
    result = filter_options(options, request)
    assert len(result) == 1
    assert result[0].departure_time.hour == 8


def test_filter_unavailable_option() -> None:
    request = TripRequest(
        origin="太原",
        destination="北京",
        travel_date=date(2026, 9, 20),
    )
    option = TransportOption(
        provider="test",
        transport_type="train",
        origin="太原",
        destination="北京",
        departure_time="2026-09-20T08:30:00",
        arrival_time="2026-09-20T11:30:00",
        price=300,
        duration_minutes=180,
        is_available=False,
    )

    assert filter_options([option], request) == []
