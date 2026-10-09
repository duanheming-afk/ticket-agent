"""订票 Agent FastAPI 入口。"""

from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from app.agent.tool_agent import ToolCallingAgent
from app.agent.parser import IntentParseError, IntentParser
from app.agent.session import ConversationStore
from app.llm.ollama_client import LLMClientError, OllamaClient
from app.orchestration.service import build_plan
from app.providers.factory import create_provider
from app.schemas import PlanResponse, TextPlanRequest, TextPlanResponse, TripRequest
from app.tools.transport import create_transport_registry
from app.web import home_page


load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MOCK_ROOT = PROJECT_ROOT / "data" / "mock"

providers = [
    create_provider("train", MOCK_ROOT / "train.json"),
    create_provider("flight", MOCK_ROOT / "flight.json"),
    create_provider("taxi", MOCK_ROOT / "taxi.json"),
]

app = FastAPI(
    title="一站式智能订票 Agent 系统",
    description="第五阶段：Provider 接入、可靠性保护、Function Calling 和硬规则过滤",
    version="0.5.0",
    docs_url="/api-docs",
    redoc_url="/api-redoc",
)

tool_agent = ToolCallingAgent(create_transport_registry(providers))
llm_client = OllamaClient()
intent_parser = IntentParser(llm_client)
conversation_store = ConversationStore()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
async def chinese_home() -> HTMLResponse:
    """中文用户界面；原 Swagger 文档迁移到 /api-docs。"""
    return home_page()


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "stage": "reliable-provider-agent",
        "provider_count": len(providers),
    }


@app.get("/providers/status")
async def provider_status() -> list[dict[str, object]]:
    """查看 Provider 模式、熔断状态和调用统计，不暴露 API Key。"""
    return [provider.status() for provider in providers]


@app.post("/plan", response_model=PlanResponse)
async def plan(request: TripRequest) -> PlanResponse:
    """并行查询 Mock Provider，再执行确定性规则过滤。"""
    return await build_plan(request, providers)


@app.post("/plan/text", response_model=TextPlanResponse)
async def plan_from_text(request: TextPlanRequest) -> TextPlanResponse:
    """解析自然语言需求，再由 Agent 选择并调用交通工具。"""
    return await _run_text_agent(request)


@app.post("/agent/plan", response_model=TextPlanResponse)
async def agent_plan(request: TextPlanRequest) -> TextPlanResponse:
    """第三阶段 Agent 主入口，/plan/text 作为兼容入口保留。"""
    return await _run_text_agent(request)


async def _run_text_agent(request: TextPlanRequest) -> TextPlanResponse:
    session_id = request.session_id or conversation_store.new_session_id()
    context = conversation_store.get(session_id)
    try:
        parsed = await intent_parser.parse(request.message, context=context)
    except (IntentParseError, LLMClientError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    missing = intent_parser.missing_fields(parsed)
    if missing:
        conversation_store.save(session_id, parsed)
        return TextPlanResponse(
            user_message=request.message,
            session_id=session_id,
            parsed_request=parsed,
            message="还缺少必要的出行信息。",
            missing_fields=missing,
            clarification=f"请补充：{'、'.join(missing)}。",
        )

    try:
        structured_request = intent_parser.to_trip_request(parsed)
        result = await tool_agent.run_with_function_calling(
            structured_request,
            request.message,
            llm_client,
        )
    except IntentParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return TextPlanResponse(
        user_message=request.message,
        session_id=session_id,
        parsed_request=parsed,
        options=result.options,
        total=result.total,
        message=result.message,
        provider_errors=result.provider_errors,
        tool_calls=result.tool_calls,
        agent_mode=result.agent_mode,
    )


@app.delete("/agent/session/{session_id}")
async def clear_session(session_id: str) -> dict[str, str]:
    """清空一个多轮对话会话。"""
    conversation_store.clear(session_id)
    return {"status": "ok", "message": "会话已清空"}
