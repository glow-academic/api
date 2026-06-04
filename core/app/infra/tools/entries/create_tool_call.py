"""Create tool call — black box that executes a tool and persists everything."""

import json
import traceback as _tb
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.tools.entries.build_call_payload import build_call_payload
from app.infra.tools.entries.create_run_message import create_run_message
from app.infra.tools.entries.save_call_upload import save_call_upload
from app.infra.tools.entries.save_text_upload import save_text_upload
from app.infra.tools.entries.types import CreateToolSetupResponse
from app.tools.entries.call_uploads.create import create_call_upload
from app.tools.entries.calls.create import create_call
from app.tools.entries.message_uploads.create import create_message_upload
from app.tools.entries.runs.create import create_run
from app.tools.entries.uploads.create import create_upload


async def create_tool_call(
    conn: asyncpg.Connection,
    redis: Redis,
    group_id: UUID,
    session_id: UUID,
    profile_id: UUID,
    upload_folder: Path,
    tool_fn: Callable[..., Any],
    arguments: dict[str, Any],
    tool_id: UUID | None = None,
    run_id: UUID | None = None,
    operation_key: UUID | None = None,
    role: str = "assistant",
    mcp: bool = False,
    raise_on_error: bool = False,
    instruction_template: str | None = None,
    on_call_created: Callable[[UUID | None], Any] | None = None,
    pre_minted_call_id: UUID | None = None,
    started_at: "datetime | None" = None,
    audit_pool: "asyncpg.Pool | None" = None,
    audit_redis: "Redis | None" = None,
) -> CreateToolSetupResponse:
    """Execute a tool and persist the full entry chain + files.

    1. Creates run + call entry chain (so call_id is available to tool_fn).
    2. Executes tool_fn(conn, call_id=call_id, **arguments) to get output.
    3. Writes .txt (always) and .json receipt (when tool_id is provided).
    4. Creates upload DB rows + junctions.
    """
    from app.infra.server_timing import timed
    # 1. Create or reuse run, create call upfront (call_id available before execution)
    if run_id is not None:
        # Reuse existing run (e.g. main generation run)
        effective_run_id = run_id
    else:
        with timed("run_insert"):
            run = await create_run(
                conn, redis,
                group_id=group_id,
                session_id=session_id,
                mcp=mcp,
            )
        effective_run_id = run.id

    call_id: UUID | None = None
    if tool_id is not None:
        with timed("call_insert"):
            call_result = await create_call(
                conn, redis,
                run_id=effective_run_id,
                session_id=session_id,
                tool_id=tool_id,
                operation_key=operation_key,
                mcp=mcp,
                id=pre_minted_call_id,
            )
        call_id = call_result.id

    # 1b. Notify caller that call record exists (for emitting "started" events)
    if on_call_created is not None:
        with timed("on_call_created_cb"):
            await on_call_created(call_id)

    # 2. Execute — call tool_fn with call_id available
    # NOTE: ``call_id`` here is the audit tool-call entry id (what create_call
    # just minted). It is namespace-distinct from any request-body field that
    # happens to also be named ``call_id`` (e.g. POST /persona/call_download
    # whose body field is the call-resource UUID to download). Strip that key
    # from the spread to avoid TypeError on duplicate kwargs. The full
    # ``arguments`` dict is preserved as-is for the audit record below.
    tool_error: Exception | None = None
    try:
        spread_args = {k: v for k, v in arguments.items() if k != "call_id"}
        with timed("tool_fn"):
            raw_result = await tool_fn(conn, call_id=call_id, **spread_args)
    except Exception as exc:
        # Capture the full failure trail into the call receipt. The
        # ``message`` + ``error_type`` fields stay shape-compatible with
        # callers that already grep them; ``traceback`` and ``context``
        # are additive and only present when the call threw. Single
        # source of truth for any post-mortem of this call.
        tool_error = exc
        raw_result = {
            "success": False,
            "message": str(exc),
            "error_type": type(exc).__name__,
            "traceback": _tb.format_exc(),
            "context": {
                "call_id": str(call_id) if call_id else None,
                "tool_id": str(tool_id) if tool_id else None,
                "run_id": str(run_id) if run_id else None,
                "session_id": str(session_id),
                "operation_key": str(operation_key) if operation_key else None,
                "instruction_template_present": bool(instruction_template),
                "arguments": arguments,
            },
        }

    # Extract canonical ID from the tool function result (cheap attr access).
    result_id: UUID | None = None
    if hasattr(raw_result, "id"):
        result_id = raw_result.id
    elif isinstance(raw_result, dict) and "id" in raw_result:
        rid = raw_result["id"]
        result_id = rid if isinstance(rid, UUID) else UUID(str(rid))

    # text_upload_id minted on critical path (used as cache row id).
    text_upload_id = uuid4()
    call_upload_id: UUID | None = call_id if tool_id is not None else None

    # Fire-and-forget the audit persistence chain (json.dumps + jinja
    # render + file IO + 5 INSERTs). Cumulative savings on the response
    # critical path:
    #   • json.dumps(raw_result) ~5-25ms (varies with response size)
    #   • template_render ~9-32ms (jinja env.from_string + render)
    #   • text_save + receipt_save ~1ms
    #   • upload_inserts + msg_insert + junction_inserts ~30ms
    # The response object doesn't need msg_id / text_id / junction_ids;
    # audit.py only reads ``result``, ``error``, ``call_id``, ``call_upload_id``.
    # Background failures log via async_tasks helper, never propagate.
    from app.utils.async_tasks import schedule_background

    schedule_background(
        _persist_audit_writes(
            session_id=session_id,
            mcp=mcp,
            role=role,
            started_at=started_at,
            run_id=effective_run_id,
            call_id=call_id,
            tool_id=tool_id,
            upload_folder=upload_folder,
            raw_result=raw_result,
            instruction_template=instruction_template,
            arguments=arguments,
            text_upload_id=text_upload_id,
            call_upload_id=call_upload_id,
            # Default None → background task reads the app-level globals
            # (production). Tests pass an on-loop pool/redis so the
            # fire-and-forget path runs against a loop-bound pool.
            pool=audit_pool,
            redis=audit_redis,
        ),
        label=f"audit_persist:tool={tool_id}",
    )

    response = CreateToolSetupResponse(
        result_id=result_id,
        result=raw_result,
        error=tool_error,
        run_id=effective_run_id,
        call_id=call_id,
        call_upload_id=call_upload_id,
        message_id=None,
        text_id=None,
        text_upload_junction_id=None,
        call_upload_junction_id=None,
        message_text_upload_junction_id=None,
        message_call_upload_junction_id=None,
    )

    if raise_on_error and tool_error is not None:
        raise tool_error

    return response


async def _persist_audit_writes(
    *,
    session_id: UUID,
    mcp: bool,
    role: str,
    started_at: "datetime | None",
    run_id: UUID,
    call_id: UUID | None,
    tool_id: UUID | None,
    upload_folder: Path,
    raw_result: Any,
    instruction_template: str | None,
    arguments: dict[str, Any],
    text_upload_id: UUID,
    call_upload_id: UUID | None,
    pool: "asyncpg.Pool | None" = None,
    redis: "Redis | None" = None,
) -> None:
    """Background-task body: serialize + render + persist audit metadata.

    Acquires its own pool conn — the caller's conn has been released by
    the time we run. Every call site is a single ``schedule_background``
    invocation; if anything here raises, the task helper logs and moves on.

    Everything in here is OFF the response critical path:
      • ``json.dumps(raw_result)`` — output_raw serialization (was 5-25ms blocking)
      • ``jinja`` render of instruction_template (was 9-32ms blocking)
      • ``save_text_upload`` + ``save_call_upload`` — disk IO
      • 5 INSERTs: text upload, call upload, msg, call_upload junction,
        message_upload junction

    ``pool`` / ``redis`` default to the app-level globals (production path —
    the ``schedule_background`` call site passes neither). They are accepted
    as explicit deps so tests can drive this on their own event loop with a
    pool bound to that loop; the process-global pool is bound to the
    session-init loop and would corrupt under asyncpg cross-loop use.
    """
    from app.infra.globals import get_pool, get_redis_client
    if pool is None:
        pool = get_pool()
    if redis is None:
        redis = get_redis_client()

    # Serialize the raw_result for audit artifacts (was blocking before
    # v1.0.51). The response object carries ``raw_result`` directly;
    # ``output_raw`` is only the .txt/.json receipt payload.
    if isinstance(raw_result, str):
        output_raw = raw_result
        raw_result_dict: Any = raw_result
    else:
        output_raw = json.dumps(raw_result, default=str)
        raw_result_dict = (
            json.loads(output_raw) if isinstance(output_raw, str) else output_raw
        )

    # Render instruction template (was blocking before v1.0.50).
    rendered_output: str | None = None
    if instruction_template:
        try:
            from jinja2 import Environment, Undefined
            env = Environment(undefined=Undefined, autoescape=False)
            tmpl = env.from_string(instruction_template)
            template_ctx = {"success": True, "results": [{"result": raw_result_dict}]}
            rendered = tmpl.render(**template_ctx).strip()
            if rendered:
                rendered_output = rendered
        except Exception:
            pass  # Fall back to raw output

    # Build text + receipt payloads (CPU-only).
    if rendered_output:
        args_lines = [f"  {k}: {v}" for k, v in arguments.items() if v is not None]
        args_section = "\n".join(args_lines) if args_lines else "  (none)"
        text_content = f"INPUT:\n{args_section}\n\nOUTPUT:\n{rendered_output}"
    else:
        text_content = output_raw

    call_payload: dict | None = None
    if tool_id is not None and call_upload_id is not None:
        output_for_json = rendered_output if rendered_output else raw_result_dict
        call_payload = build_call_payload(
            call_id=call_upload_id,
            tool_id=tool_id,
            arguments=arguments,
            output=output_for_json,
            raw_output=raw_result_dict,
        )

    # File IO (sync Python disk write, ~1ms total — too small to threadpool)
    text_rel_path = save_text_upload(text_content, text_upload_id, upload_folder)
    text_size = (upload_folder / text_rel_path).stat().st_size

    call_rel_path: str | None = None
    call_size = 0
    if call_payload is not None and call_upload_id is not None:
        call_rel_path = save_call_upload(call_payload, call_upload_id, upload_folder)
        call_size = (upload_folder / call_rel_path).stat().st_size

    async with pool.acquire() as conn:
        # Atomic composite: the audit uploads + message subtree + call/message
        # junctions must land together or not at all. asyncpg autocommits each
        # statement, so without this boundary a failure on a later insert (e.g.
        # create_call_upload) after the message subtree already committed would
        # leave uploads + message WITHOUT the linking junction — a partial-write
        # orphan on the always-hit audited-tool-call path, visible to reads and
        # unable to self-heal. create_run_message opens its own transaction;
        # asyncpg nests it as a SAVEPOINT under this outer one, so they compose.
        async with conn.transaction():
            text_upload = await create_upload(
                conn, redis,
                session_id=session_id,
                file_path=text_rel_path,
                mime_type="text/plain",
                size=text_size,
                mcp=mcp,
            )

            call_upload_db_id: UUID | None = None
            if tool_id is not None and call_rel_path is not None:
                call_upload = await create_upload(
                    conn, redis,
                    session_id=session_id,
                    file_path=call_rel_path,
                    mime_type="application/json",
                    size=call_size,
                    mcp=mcp,
                )
                call_upload_db_id = call_upload.id

            msg = await create_run_message(
                conn,
                redis,
                run_id=run_id,
                session_id=session_id,
                role=role,
                upload_id=text_upload.id,
                mcp=mcp,
                created_at=started_at,
            )

            if call_id is not None and call_upload_db_id is not None:
                await create_call_upload(
                    conn, redis,
                    call_id=call_id,
                    upload_id=call_upload_db_id,
                    session_id=session_id,
                    mcp=mcp,
                )
                await create_message_upload(
                    conn, redis,
                    message_id=msg.message_id,
                    upload_id=call_upload_db_id,
                    session_id=session_id,
                    mcp=mcp,
                )
