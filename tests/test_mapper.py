from datetime import date

from app.providers.mapper import TransportOptionMapper
from app.schemas import TripRequest


def test_mapper_converts_external_fields_to_transport_option() -> None:
    request = TripRequest(
        origin="太原",
        destination="北京",
        travel_date=date(2026, 9, 20),
    )
    payload = {
        "data": {
            "items": [
                {
                    "from": "太原",
                    "to": "北京",
                    "departAt": "2026-09-20T08:30:00",
                    "arriveAt": "2026-09-20T11:45:00",
                    "fare": "267",
                    "remaining": 3,
                    "seat": "二等座",
                }
            ]
        }
    }
    mapper = TransportOptionMapper(
        items_path="data.items",
        field_map={
            "departure_time": "departAt",
            "arrival_time": "arriveAt",
        },
    )

    options = mapper.map_response(
        payload,
        provider="real_train",
        transport_type="train",
        request=request,
    )

    assert len(options) == 1
    assert options[0].price == 267
    assert options[0].ticket_count == 3
    assert options[0].seat_type == "二等座"
    assert options[0].is_available is True
