"""Helpers for resolving tools and recording call arg values."""

from uuid import UUID

import asyncpg  # type: ignore


class ToolArgInfo:
    """Single arg definition from a tool's args_ids."""

    def __init__(self, args_id: UUID, name: str, field_type: str) -> None:
        self.args_id = args_id
        self.name = name
        self.field_type = field_type


class ToolInfo:
    """Resolved tool with its args."""

    def __init__(self, tool_id: UUID, args: list[ToolArgInfo]) -> None:
        self.tool_id = tool_id
        self.args = args


async def record_call_args(
    conn: asyncpg.Connection,
    call_id: UUID,
    tool_info: ToolInfo,
    request_dict: dict,
    mcp: bool = False,
) -> None:
    """No-op — calls_args_entry and calls_args_args_connection were dropped in migration 29.

    Kept as a no-op so existing callers don't break. Will be removed in Phase 2.
    """
