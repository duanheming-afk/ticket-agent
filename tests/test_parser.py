import pytest

from app.agent.parser import IntentParser


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response

    async def chat(self, system_prompt: str, user_message: str) -> str:
        return self.response


@pytest.mark.asyncio
async def test_parse_complete_trip_request() -> None:
    client = FakeLLMClient(
        '{"origin":"太原","destination":"北京",'
        '"travel_date":"2026-09-20","depart_after":"08:00",'
        '"budget":500,"transport_types":["高铁"],'
        '"allow_transfer":false,"max_transfers":0,"preference":"优先高铁"}'
    )
    parser = IntentParser(client)

    parsed = await parser.parse("9月20日太原去北京，不接受中转")

    assert parsed.origin == "太原"
    assert parsed.destination == "北京"
    assert parsed.transport_types == ["train"]
    assert parsed.allow_transfer is False
    assert parser.missing_fields(parsed) == []


@pytest.mark.asyncio
async def test_missing_required_fields_can_be_used_for_clarification() -> None:
    client = FakeLLMClient('{"destination":"北京"}')
    parser = IntentParser(client)

    parsed = await parser.parse("我想去北京")

    assert parser.missing_fields(parsed) == ["出发地", "出发日期"]
