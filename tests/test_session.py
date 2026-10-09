from datetime import date

from app.agent.session import ConversationStore
from app.schemas import ParsedTripRequest


def test_conversation_store_saves_and_clears_session() -> None:
    store = ConversationStore()
    session_id = store.new_session_id()
    parsed = ParsedTripRequest(
        origin="太原",
        destination="北京",
        travel_date=date(2026, 9, 20),
    )

    store.save(session_id, parsed)
    assert store.get(session_id) == parsed
    store.clear(session_id)
    assert store.get(session_id) is None
