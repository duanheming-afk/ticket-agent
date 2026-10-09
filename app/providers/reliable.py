"""Provider 超时、重试和熔断保护。"""

from __future__ import annotations

import asyncio
import time

from app.providers.base import TransportProvider
from app.schemas import TransportOption, TripRequest


class ProviderCallError(RuntimeError):
    """Provider 多次调用失败。"""


class CircuitOpenError(RuntimeError):
    """Provider 处于熔断状态，暂时跳过调用。"""


class ReliableProvider:
    """为任意 Provider 增加超时、指数退避重试和简单熔断。"""

    def __init__(
        self,
        provider: TransportProvider,
        *,
        timeout_seconds: float = 8.0,
        max_retries: int = 2,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        retry_backoff_seconds: float = 0.2,
    ) -> None:
        self.provider = provider
        self.name = provider.name
        self.transport_type = provider.transport_type
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.retry_backoff_seconds = retry_backoff_seconds
        self._failure_count = 0
        self._opened_at: float | None = None
        self._total_calls = 0
        self._success_calls = 0
        self._failed_calls = 0
        self._retry_count = 0

    async def search(self, request: TripRequest) -> list[TransportOption]:
        self._check_circuit()
        self._total_calls += 1
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self.provider.search(request), timeout=self.timeout_seconds
                )
                self._failure_count = 0
                self._opened_at = None
                self._success_calls += 1
                return result
            except Exception as exc:  # Provider 故障必须被隔离在本工具内
                last_error = exc
                if attempt < self.max_retries:
                    self._retry_count += 1
                    delay = self.retry_backoff_seconds * (2**attempt)
                    if delay:
                        await asyncio.sleep(delay)

        self._record_failure()
        self._failed_calls += 1
        detail = str(last_error) or type(last_error).__name__
        raise ProviderCallError(
            f"{self.name} 调用失败，已重试 {self.max_retries} 次：{detail}"
        ) from last_error

    def _check_circuit(self) -> None:
        if self._opened_at is None:
            return
        elapsed = time.monotonic() - self._opened_at
        if elapsed < self.cooldown_seconds:
            raise CircuitOpenError(
                f"{self.name} 已熔断，{self.cooldown_seconds - elapsed:.1f} 秒后重试"
            )
        self._opened_at = None
        self._failure_count = 0

    def _record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._opened_at = time.monotonic()

    @property
    def circuit_state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if time.monotonic() - self._opened_at >= self.cooldown_seconds:
            return "half_open"
        return "open"

    def status(self) -> dict[str, object]:
        mode = getattr(self.provider, "mode", None)
        if mode is None:
            mode = "http" if self.provider.__class__.__name__ == "HttpJsonProvider" else "mock"
        return {
            "name": self.name,
            "transport_type": self.transport_type,
            "mode": mode,
            "circuit_state": self.circuit_state,
            "failure_count": self._failure_count,
            "total_calls": self._total_calls,
            "success_calls": self._success_calls,
            "failed_calls": self._failed_calls,
            "retry_count": self._retry_count,
        }
