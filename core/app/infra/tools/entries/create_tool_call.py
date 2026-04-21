"""Create tool call — black box that executes a tool and persists everything."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import asyncpg  # type: ignore

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
) -> CreateToolSetupResponse:
    """Execute a tool and persist the full entry chain + files.

    1. Creates run + call entry chain (so call_id is available to tool_fn).
    2. Executes tool_fn(conn, call_id=call_id, **arguments) to get output.
    3. Writes .txt (always) and .json receipt (when tool_id is provided).
    4. Creates upload DB rows + junctions.
    """
    # 1. Create or reuse run, create call upfront (call_id available before execution)
    if run_id is not None:
        # Reuse existing run (e.g. main generation run)
        effective_run_id = run_id
    else:
        run = await create_run(
            conn,
            group_id=group_id,
            session_id=session_id,
            mcp=mcp,
        )
        effective_run_id = run.id

    call_id: UUID | None = None
    if tool_id is not None:
        call_result = await create_call(
            conn,
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
        await on_call_created(call_id)

    # 2. Execute — call tool_fn with call_id available
    tool_error: Exception | None = None
    try:
        raw_result = await tool_fn(conn, call_id=call_id, **arguments)
    except Exception as exc:
        tool_error = exc
        raw_result = {"success": False, "message": str(exc)}

    if isinstance(raw_result, str):
        output_raw = raw_result
    else:
        output_raw = json.dumps(raw_result, default=str)

    # Extract canonical ID from the tool function result
    result_id: UUID | None = None
    if hasattr(raw_result, "id"):
        result_id = raw_result.id
    elif isinstance(raw_result, dict) and "id" in raw_result:
        rid = raw_result["id"]
        result_id = rid if isinstance(rid, UUID) else UUID(str(rid))

    # 2b. Render instruction template (Layer 3) if available
    rendered_output: str | None = None
    if instruction_template:
        try:
            from jinja2 import Environment, Undefined
            env = Environment(undefined=Undefined, autoescape=False)
            tmpl = env.from_string(instruction_template)
            # Wrap in {success, results} structure that templates expect.
            result_dict = (
                json.loads(output_raw) if isinstance(output_raw, str)
                else output_raw
            )
            template_ctx = {
                "success": True,
                "results": [{"result": result_dict}],
            }
            rendered = tmpl.render(**template_ctx).strip()
            if rendered:
                rendered_output = rendered
        except Exception:
            pass  # Fall back to raw output

    # 3. Write .txt — rendered template with INPUT/OUTPUT if available
    text_upload_id = uuid4()
    if rendered_output:
        # Format arguments concisely
        args_lines = []
        for k, v in arguments.items():
            if v is not None:
                args_lines.append(f"  {k}: {v}")
        args_section = "\n".join(args_lines) if args_lines else "  (none)"
        text_content = f"INPUT:\n{args_section}\n\nOUTPUT:\n{rendered_output}"
    else:
        text_content = output_raw
    text_rel_path = save_text_upload(text_content, text_upload_id, upload_folder)
    text_full_path = upload_folder / text_rel_path
    text_size = text_full_path.stat().st_size

    # 4. Write .json receipt (only with tool_id)
    call_upload_id: UUID | None = None
    call_upload_db_id: UUID | None = None
    if tool_id is not None:
        call_upload_id = call_id
        # Use rendered output string if available, raw dict otherwise
        if rendered_output:
            output_for_json = rendered_output
        else:
            output_for_json = (
                json.loads(output_raw) if isinstance(output_raw, str)
                else output_raw
            )
        # raw_output: full API response for idempotent playback
        raw_output_dict = (
            json.loads(output_raw) if isinstance(output_raw, str)
            else output_raw
        )
        payload = build_call_payload(
            call_id=call_upload_id,
            tool_id=tool_id,
            arguments=arguments,
            output=output_for_json,
            raw_output=raw_output_dict,
        )
        call_rel_path = save_call_upload(payload, call_upload_id, upload_folder)
        call_full_path = upload_folder / call_rel_path
        call_size = call_full_path.stat().st_size

    # 5. Create upload DB rows
    text_upload = await create_upload(
        conn,
        session_id=session_id,
        file_path=text_rel_path,
        mime_type="text/plain",
        size=text_size,
        mcp=mcp,
    )

    if tool_id is not None and call_upload_db_id is None:
        call_upload = await create_upload(
            conn,
            session_id=session_id,
            file_path=call_rel_path,
            mime_type="application/json",
            size=call_size,
            mcp=mcp,
        )
        call_upload_db_id = call_upload.id

    # 6. Text message path (always)
    msg = await create_run_message(
        conn,
        run_id=effective_run_id,
        session_id=session_id,
        role=role,
        upload_id=text_upload.id,
        mcp=mcp,
    )

    # 7. Call upload junctions (only when tool_id is provided)
    call_upload_junction_id: UUID | None = None
    message_call_upload_junction_id: UUID | None = None

    if call_id is not None and call_upload_db_id is not None:
        call_upload_junction = await create_call_upload(
            conn,
            call_id=call_id,
            upload_id=call_upload_db_id,
            session_id=session_id,
            mcp=mcp,
        )
        call_upload_junction_id = call_upload_junction.id

        msg_call_upload = await create_message_upload(
            conn,
            message_id=msg.message_id,
            upload_id=call_upload_db_id,
            session_id=session_id,
            mcp=mcp,
        )
        message_call_upload_junction_id = msg_call_upload.id

    response = CreateToolSetupResponse(
        result_id=result_id,
        result=raw_result,
        run_id=effective_run_id,
        call_id=call_id,
        call_upload_id=call_upload_id,
        message_id=msg.message_id,
        text_id=msg.text_id,
        text_upload_junction_id=msg.text_upload_junction_id,
        call_upload_junction_id=call_upload_junction_id,
        message_text_upload_junction_id=msg.message_upload_junction_id,
        message_call_upload_junction_id=message_call_upload_junction_id,
    )

    if raise_on_error and tool_error is not None:
        raise tool_error

    return response
