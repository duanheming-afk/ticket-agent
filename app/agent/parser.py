"""将自然语言出行需求解析为可校验的结构化字段。"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from app.llm.base import LLMClient
from app.schemas import ParsedTripRequest, TripRequest


class IntentParseError(RuntimeError):
    """自然语言解析失败。"""


REQUIRED_FIELDS = {
    "origin": "出发地",
    "destination": "目的地",
    "travel_date": "出发日期",
}

TRANSPORT_ALIASES = {
    "train": {"train", "高铁", "动车", "火车", "铁路", "列车"},
    "flight": {"flight", "飞机", "航班", "航空"},
    "taxi": {"taxi", "出租车", "打车", "网约车"},
}


def build_parser_prompt(
    today: date,
    context: ParsedTripRequest | None = None,
) -> str:
    context_text = "无"
    if context is not None:
        context_text = json.dumps(
            context.model_dump(exclude_none=True), ensure_ascii=False
        )
    return f"""你是订票系统的意图解析器。今天是 {today.isoformat()}。
只从用户文本中提取出行条件，必须只返回一个 JSON 对象，不要输出 Markdown、解释或额外文字。
JSON 字段必须使用以下名称：
origin、destination、travel_date、depart_after、budget、transport_types、
allow_transfer、max_transfers、preference。

已有会话条件：{context_text}
如果已有会话条件不为空，本轮没有修改的字段必须保留；用户明确修改的字段使用新值。

规则：
1. 无法确定的值返回 null；不要擅自猜测出发地、目的地、日期或预算。
2. travel_date 使用 YYYY-MM-DD，depart_after 使用 HH:MM。
3. 交通方式只使用 train、flight、taxi；未指定时 transport_types 返回 null。
4. “不接受中转”对应 allow_transfer=false、max_transfers=0。
5. “预算500以内”对应 budget=500。
6. “明天”“下周一”等相对日期，根据今天换算成具体日期。
"""


def _extract_json(text: str) -> dict[str, Any]:
    """兼容模型偶尔返回 Markdown 代码块或附加解释的情况。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise IntentParseError("模型没有返回有效的 JSON。") from None
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise IntentParseError("模型返回的 JSON 无法解析。") from exc
    if not isinstance(value, dict):
        raise IntentParseError("模型返回结果必须是 JSON 对象。")
    return value


def _normalize_transport_types(
    transport_types: list[str] | None,
) -> list[str] | None:
    if not transport_types:
        return None
    normalized: list[str] = []
    for item in transport_types:
        item_lower = item.strip().lower()
        for transport_type, aliases in TRANSPORT_ALIASES.items():
            if item_lower in {alias.lower() for alias in aliases}:
                if transport_type not in normalized:
                    normalized.append(transport_type)
                break
    return normalized or None


def _infer_explicit_transport_types(message: str) -> list[str] | None:
    """对有限枚举交通方式做确定性校正，避免小模型混淆高铁和飞机。"""
    rules = (
        ("train", ("高铁", "动车", "火车", "铁路", "列车")),
        ("flight", ("飞机", "航班", "航空")),
        ("taxi", ("出租车", "打车", "网约车")),
    )
    found = [transport for transport, words in rules if any(word in message for word in words)]
    return found or None


def _apply_deterministic_constraints(
    parsed: ParsedTripRequest,
    message: str,
    context: ParsedTripRequest | None,
) -> ParsedTripRequest:
    explicit_types = _infer_explicit_transport_types(message)
    if explicit_types:
        parsed.transport_types = explicit_types
    elif context is not None and context.transport_types:
        parsed.transport_types = context.transport_types

    if any(word in message for word in ("不接受中转", "不要中转", "不允许中转", "直达")):
        parsed.allow_transfer = False
        parsed.max_transfers = 0
    elif any(word in message for word in ("可以中转", "接受中转", "允许中转")):
        parsed.allow_transfer = True
        if parsed.max_transfers is None:
            parsed.max_transfers = 1
    elif context is not None:
        parsed.allow_transfer = context.allow_transfer
        parsed.max_transfers = context.max_transfers
    else:
        # 模型没有得到明确约束时，保留“未知”，由 TripRequest 使用默认规则。
        parsed.allow_transfer = None
        parsed.max_transfers = None
    return parsed


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """处理小模型常见的轻微格式偏差，再交给 Pydantic 做严格校验。"""
    normalized = dict(payload)
    transport_types = normalized.get("transport_types")
    if isinstance(transport_types, str):
        normalized["transport_types"] = [transport_types]
    return normalized


class IntentParser:
    def __init__(self, client: LLMClient) -> None:
        self.client = client

    async def parse(
        self,
        user_message: str,
        context: ParsedTripRequest | None = None,
    ) -> ParsedTripRequest:
        raw = await self.client.chat(
            build_parser_prompt(date.today(), context), user_message
        )
        payload = _normalize_payload(_extract_json(raw))
        try:
            parsed = ParsedTripRequest.model_validate(payload)
        except ValueError as exc:
            raise IntentParseError(f"模型提取出的字段不符合格式：{exc}") from exc

        parsed.transport_types = _normalize_transport_types(parsed.transport_types)
        if context is not None:
            previous = context.model_dump(exclude_none=True)
            current = parsed.model_dump(exclude_none=True)
            previous.update(current)
            parsed = ParsedTripRequest.model_validate(previous)
        return _apply_deterministic_constraints(parsed, user_message, context)

    @staticmethod
    def missing_fields(parsed: ParsedTripRequest) -> list[str]:
        return [
            label
            for field, label in REQUIRED_FIELDS.items()
            if getattr(parsed, field) is None
        ]

    @staticmethod
    def to_trip_request(parsed: ParsedTripRequest) -> TripRequest:
        missing = IntentParser.missing_fields(parsed)
        if missing:
            raise IntentParseError(f"缺少必要信息：{', '.join(missing)}")
        data = parsed.model_dump(exclude_none=True)
        data.setdefault("transport_types", ["train", "flight", "taxi"])
        data.setdefault("allow_transfer", True)
        data.setdefault("max_transfers", 1)
        if data["allow_transfer"] is False:
            data["max_transfers"] = 0
        return TripRequest.model_validate(data)
