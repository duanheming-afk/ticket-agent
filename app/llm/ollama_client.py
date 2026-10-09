"""Ollama 本地模型客户端。"""

from __future__ import annotations

import os
from typing import Any

import httpx


class LLMClientError(RuntimeError):
    """LLM 调用或响应格式异常。"""


class OllamaClient:
    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.host = (host or os.getenv("LLM_HOST", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model or os.getenv("LLM_MODEL", "qwen2.5:3b")
        self.timeout = timeout

    async def chat(self, system_prompt: str, user_message: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.host}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMClientError(
                f"无法连接 Ollama，请检查服务和模型：{self.host} / {self.model}"
            ) from exc

        try:
            data = response.json()
            content = data["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMClientError("Ollama 返回结果格式不正确。") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMClientError("Ollama 返回了空内容。")
        return content

    async def chat_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """调用 Ollama 原生工具调用接口，返回 assistant message。"""
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "tools": tools,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.host}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMClientError(
                f"Ollama 原生工具调用失败：{self.host} / {self.model}"
            ) from exc

        try:
            data = response.json()
            message = data["message"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMClientError("Ollama 工具调用返回结果格式不正确。") from exc
        if not isinstance(message, dict):
            raise LLMClientError("Ollama 工具调用没有返回有效消息。")
        return message
