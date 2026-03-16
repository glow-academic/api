import asyncio
from typing import Any

import asyncpg  # type: ignore


def extract_debug_context(ctx: Any) -> tuple[object | None, object | None]:
    """Extract run_id and conn from a variety of context shapes."""
    if hasattr(ctx, "context"):
        return ctx.context.run_id, ctx.context.conn
    if isinstance(ctx, dict):
        return ctx.get("run_id"), ctx.get("conn")
    return getattr(ctx, "run_id", None), getattr(ctx, "conn", None)


async def debug_info(ctx: Any, content: str) -> str:
    """
    Meta-prompting/debug tool for the assistant.

    Call this tool whenever you are blocked, confused, or uncertain about how to
    proceed with the user's request (e.g., ambiguous instructions, missing inputs,
    conflicting constraints, or external/API failures). Pass a short, clear note
    in `content` that describes:
    - what you were trying to do,
    - what is unclear or failing,
    - what you need to continue,
    - any assumptions you are considering.

    The note is saved as a problem entry for human review and troubleshooting.
    It is safe to call multiple times. Do not include secrets or large payloads.
    This tool does not reply to the user; it only logs context and returns a
    confirmation string.
    """
    run_id, conn = extract_debug_context(ctx)

    if not run_id or not conn:
        return "Error: Missing run_id or conn in context"

    try:
        asyncio.create_task(_insert_problem_from_run(conn, run_id, content))
    except Exception as e:
        print(f"Error saving problem: {e}")
        return f"Error saving problem: {e}"
    return "Saved debug info"


async def _insert_problem_from_run(
    conn: asyncpg.Connection, run_id: object, content: str
) -> None:
    """Insert a problem entry from a run context (fire-and-forget)."""
    await conn.execute(
        """
        SELECT * FROM infra_insert_problem_from_run_v4($1, $2)
        """,
        run_id,
        content,
    )
