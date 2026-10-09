"""交通查询工具注册。"""

from __future__ import annotations

from app.providers.base import TransportProvider
from app.tools.registry import ToolRegistry, ToolSpec


def create_transport_registry(
    providers: list[TransportProvider],
) -> ToolRegistry:
    specs = [
        ToolSpec(
            name=f"search_{provider.transport_type}",
            description=f"查询{provider.transport_type}出行方案",
            transport_type=provider.transport_type,
            provider=provider,
        )
        for provider in providers
    ]
    return ToolRegistry(specs)
