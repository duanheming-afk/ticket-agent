"""第三阶段 Agent：选择并调用交通查询工具。"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from app.schemas import ToolCallRecord, TransportOption, TripRequest
from app.tools.registry import ToolRegistry
from app.validation.hard_rules import filter_options


@dataclass
class AgentPlanResult:
    options: list[TransportOption]
    total: int
    message: str
    provider_errors: list[str]
    tool_calls: list[ToolCallRecord]
    agent_mode: str = "deterministic-tool-selection"


class ToolCallingAgent:
    """根据已校验的交通类型选择工具，并并发执行工具调用。"""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def select_tools(self, request: TripRequest) -> list[str]:
        """根据用户允许的交通方式选择白名单工具。"""
        allowed_types = set(request.transport_types)
        return [
            spec.name
            for spec in self.registry.list_tools()
            if spec.transport_type in allowed_types
        ]

    async def run(
        self,
        request: TripRequest,
        tool_names: list[str] | None = None,
        agent_mode: str = "deterministic-tool-selection",
    ) -> AgentPlanResult:
        tool_names = tool_names if tool_names is not None else self.select_tools(request)
        results = await asyncio.gather(
            *(self.registry.execute(name, request) for name in tool_names),
            return_exceptions=True,
        )

        options: list[TransportOption] = []
        errors: list[str] = []
        tool_calls: list[ToolCallRecord] = []
        for name, result in zip(tool_names, results, strict=True):
            if isinstance(result, Exception):
                message = str(result)
                errors.append(f"{name}: {message}")
                tool_calls.append(
                    ToolCallRecord(
                        name=name,
                        status="error",
                        error=message,
                    )
                )
            else:
                options.extend(result)
                tool_calls.append(
                    ToolCallRecord(
                        name=name,
                        status="success",
                        result_count=len(result),
                    )
                )

        valid_options = filter_options(options, request)
        message = "找到符合条件的出行方案。" if valid_options else "没有找到符合条件的方案。"
        return AgentPlanResult(
            options=valid_options,
            total=len(valid_options),
            message=message,
            provider_errors=errors,
            tool_calls=tool_calls,
            agent_mode=agent_mode,
        )

    async def run_with_function_calling(
        self,
        request: TripRequest,
        user_message: str,
        llm_client: Any,
    ) -> AgentPlanResult:
        """优先使用模型原生 tool_calls；模型不支持时安全降级。"""
        system_prompt = (
            "你是交通工具路由器。请根据已经校验的出行条件选择查询工具。"
            "只能调用工具，不能直接回答用户。只能选择允许的交通方式。"
        )
        structured = json.dumps(request.model_dump(mode="json"), ensure_ascii=False)
        routing_message = (
            f"用户原始需求：{user_message}\n"
            f"已经校验的结构化条件：{structured}\n"
            "请调用一个或多个合适的交通查询工具。"
        )
        try:
            message = await llm_client.chat_with_tools(
                system_prompt,
                routing_message,
                self.registry.function_definitions(),
            )
            calls = message.get("tool_calls", [])
            allowed_names = set(self.select_tools(request))
            selected: list[str] = []
            for call in calls:
                function = call.get("function", {})
                name = function.get("name")
                if name in allowed_names and name not in selected:
                    selected.append(name)
            if selected:
                return await self.run(
                    request,
                    tool_names=selected,
                    agent_mode="ollama-function-calling",
                )
        except Exception:
            # 原生工具调用不是所有本地模型都支持，不能影响基础订票能力。
            pass
        return await self.run(request, agent_mode="deterministic-fallback")
