"""订票 Agent 的请求、解析结果和交通方案数据模型。"""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, Field, field_validator


class TripRequest(BaseModel):
    """已经完成校验、可以交给 Provider 查询的结构化出行需求。"""

    origin: str = Field(min_length=1, description="出发地")
    destination: str = Field(min_length=1, description="目的地")
    travel_date: date = Field(description="出发日期")
    depart_after: time | None = Field(default=None, description="最早出发时间")
    budget: float | None = Field(default=None, ge=0, description="预算上限")
    transport_types: list[str] = Field(
        default_factory=lambda: ["train", "flight", "taxi"],
        description="允许的交通方式",
    )
    allow_transfer: bool = True
    max_transfers: int = Field(default=1, ge=0, le=3)
    preference: str | None = None

    @field_validator("origin", "destination")
    @classmethod
    def strip_location(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("地点不能为空")
        return value


class TransportOption(BaseModel):
    """不同 Provider 统一后的交通方案。"""

    provider: str
    transport_type: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    price: float = Field(ge=0)
    duration_minutes: int = Field(gt=0)
    transfers: int = Field(default=0, ge=0)
    ticket_count: int | None = Field(default=None, ge=0, description="剩余票数")
    seat_type: str | None = Field(default=None, description="座位或舱位类型")
    is_available: bool = Field(default=True, description="是否可以预订")
    booking_url: str | None = None


class PlanResponse(BaseModel):
    """结构化请求接口响应。"""

    request: TripRequest
    options: list[TransportOption]
    total: int
    message: str
    provider_errors: list[str] = Field(default_factory=list)


class ParsedTripRequest(BaseModel):
    """LLM 提取出的出行需求，必填字段允许为空以支持追问。"""

    origin: str | None = Field(default=None, description="出发地")
    destination: str | None = Field(default=None, description="目的地")
    travel_date: date | None = Field(default=None, description="出发日期")
    depart_after: time | None = Field(default=None, description="最早出发时间")
    budget: float | None = Field(default=None, ge=0, description="预算上限")
    transport_types: list[str] | None = Field(
        default=None, description="允许的交通方式"
    )
    allow_transfer: bool | None = None
    max_transfers: int | None = Field(default=None, ge=0, le=3)
    preference: str | None = None

    @field_validator("origin", "destination")
    @classmethod
    def strip_optional_location(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TextPlanRequest(BaseModel):
    """自然语言订票请求。"""

    message: str = Field(min_length=1, description="用户的自然语言出行需求")
    session_id: str | None = Field(default=None, description="多轮对话会话 ID")

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("出行需求不能为空")
        return value


class TextPlanResponse(BaseModel):
    """自然语言接口响应，包含解析结果和追问信息。"""

    user_message: str
    session_id: str
    parsed_request: ParsedTripRequest
    options: list[TransportOption] = Field(default_factory=list)
    total: int = 0
    message: str
    missing_fields: list[str] = Field(default_factory=list)
    clarification: str | None = None
    provider_errors: list[str] = Field(default_factory=list)
    tool_calls: list["ToolCallRecord"] = Field(default_factory=list)
    agent_mode: str = "deterministic-tool-selection"


class ToolCallRecord(BaseModel):
    """一次工具调用的可观测记录。"""

    name: str
    status: str
    result_count: int = 0
    error: str | None = None
