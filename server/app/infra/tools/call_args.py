"""Helpers for resolving tools and recording call arg values."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.globals import get_redis_client
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


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


async def resolve_tool(
    conn: asyncpg.Connection,
    operation: str,
    target: str,
    *,
    scope: str = "entries",
) -> ToolInfo | None:
    """Resolve tool_id + args by operation and target.

    Looks up tools_resource by operation + target across the appropriate
    scope column (entries, resources, or artifacts).

    Args:
        operation: Tool operation (e.g. "create", "link")
        target: Target type (e.g. "attempts", "names", "agent")
        scope: Which column to match — "entries", "resources", or "artifacts"
    """
    cache_key = f"tool_info:{scope}:{operation}:{target}"
    cached = await get_cached(cache_key, redis=get_redis_client())
    if cached:
        return ToolInfo(
            tool_id=UUID(cached["tool_id"]),
            args=[
                ToolArgInfo(
                    args_id=UUID(a["args_id"]),
                    name=a["name"],
                    field_type=a["field_type"],
                )
                for a in cached.get("args", [])
            ],
        )

    if scope not in ("entries", "resources", "artifacts"):
        return None

    row = await conn.fetchrow(
        f"""
        SELECT id, args_ids
        FROM tools_resource
        WHERE operation = $1
          AND $2 = ANY({scope})
          AND active = true
        LIMIT 1
        """,
        operation,
        target,
    )
    if not row:
        return None

    tool_id = row["id"]
    args_ids = row["args_ids"] or []

    args: list[ToolArgInfo] = []
    if args_ids:
        arg_rows = await conn.fetch(
            """
            SELECT id, name, field_type
            FROM args_resource
            WHERE id = ANY($1::uuid[])
              AND active = true
            """,
            args_ids,
        )
        args = [
            ToolArgInfo(
                args_id=r["id"],
                name=r["name"],
                field_type=r["field_type"],
            )
            for r in arg_rows
        ]

    tool_info = ToolInfo(tool_id=tool_id, args=args)
    await set_cached(
        cache_key,
        {
            "tool_id": str(tool_id),
            "args": [
                {"args_id": str(a.args_id), "name": a.name, "field_type": a.field_type}
                for a in args
            ],
        },
        ttl=3600,
        tags=["tools"],
        redis=get_redis_client(),
    )
    return tool_info


# Backwards-compatible alias for existing entry callers
async def resolve_tool_for_entry(
    conn: asyncpg.Connection,
    operation: str,
    entry_type: str,
) -> ToolInfo | None:
    """Resolve tool for an entry type. Delegates to resolve_tool."""
    return await resolve_tool(conn, operation, entry_type, scope="entries")


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
