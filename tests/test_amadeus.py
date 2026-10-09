from datetime import date

from app.providers.amadeus import AmadeusFlightProvider, _duration_minutes, _location_code
from app.schemas import TripRequest


def test_amadeus_location_and_duration_helpers() -> None:
    assert _location_code("太原") == "TYN"
    assert _location_code("pek") == "PEK"
    assert _duration_minutes("PT2H35M") == 155


def test_amadeus_response_maps_to_transport_option() -> None:
    request = TripRequest(
        origin="太原",
        destination="北京",
        travel_date=date(2026, 9, 20),
        transport_types=["flight"],
    )
    payload = {
        "data": [
            {
                "numberOfBookableSeats": 5,
                "price": {"grandTotal": "680.00"},
                "itineraries": [
                    {
                        "duration": "PT2H35M",
                        "segments": [
                            {
                                "departure": {"at": "2026-09-20T09:00:00+08:00"},
                                "arrival": {"at": "2026-09-20T11:35:00+08:00"},
                            }
                        ],
                    }
                ],
                "travelerPricings": [
                    {"fareDetailsBySegment": [{"cabin": "ECONOMY"}]}
                ],
            }
        ]
    }

    options = AmadeusFlightProvider("id", "secret").map_response(payload, request)

    assert len(options) == 1
    assert options[0].provider == "amadeus_flight"
    assert options[0].price == 680
    assert options[0].duration_minutes == 155
    assert options[0].ticket_count == 5
    assert options[0].seat_type == "ECONOMY"
