"""Shared resolver for the unified per-arg ``args_drafts`` payload.

Both the ``/tool/draft`` (staging) surface and the ``/tool/create`` +
``/tool/update`` surfaces accept ``args_drafts`` — a list of per-arg draft
rows (name/type/description/required/default + nested outputs). The client's
``Tool.tsx`` sends this on create AND update; before the cross-repo hunt
batch only the draft model accepted it, so new tools were created with zero
arguments and edits were discarded.

This helper is the single black box that turns ``args_drafts`` into the
flat ``(arg_ids, output_ids, position_ids)`` id triple. It creates/re-links
each arg, its nested outputs (scoped to the resolved args_id), and a
per-``(args_id, value=index)`` position row — exactly mirroring the original
draft-only inline logic.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.tool.types import ToolArgDraftValue
from app.tools.resources.arg_positions.create import create_arg_position
from app.tools.resources.args.create import create_arg
from app.tools.resources.args_outputs.create import create_args_output


async def resolve_arg_drafts(
    conn: asyncpg.Connection,
    redis: Redis,
    args_drafts: list[ToolArgDraftValue],
    *,
    arg_ids: list[UUID] | None = None,
    output_ids: list[UUID] | None = None,
    position_ids: list[UUID] | None = None,
) -> tuple[list[UUID], list[UUID], list[UUID]]:
    """Resolve ``args_drafts`` to the flat id triple (mutates draft ids in place).

    Each entry maps 1:1 to a row; saved rows (``id`` present) are re-linked
    unchanged, new rows are created. The supplied seed id lists are merged
    with (not replaced by) the resolved ids. Returns
    ``(merged_arg_ids, merged_output_ids, merged_position_ids)``.
    """
    merged_arg_ids: list[UUID] = list(arg_ids or [])
    merged_output_ids: list[UUID] = list(output_ids or [])
    merged_pos_ids: list[UUID] = list(position_ids or [])

    for index, arg_draft in enumerate(args_drafts):
        # Resolve the arg row (create or re-link).
        if arg_draft.id is not None:
            resolved_arg_id: UUID = arg_draft.id
        else:
            new_arg = await create_arg(
                conn,
                name=arg_draft.name,
                field_type=arg_draft.field_type,
                redis=redis,
                description=arg_draft.description,
                required=arg_draft.required,
                default_value=arg_draft.default_value,
            )
            resolved_arg_id = new_arg.id
            arg_draft.id = resolved_arg_id
        if resolved_arg_id not in merged_arg_ids:
            merged_arg_ids.append(resolved_arg_id)

        # Resolve nested outputs (scoped to the resolved args_id).
        for output_draft in arg_draft.outputs or []:
            if output_draft.id is not None:
                if output_draft.id not in merged_output_ids:
                    merged_output_ids.append(output_draft.id)
                continue
            new_output = await create_args_output(
                conn,
                args_id=resolved_arg_id,
                name=output_draft.name,
                redis=redis,
                template=output_draft.template,
            )
            output_draft.id = new_output.id
            if new_output.id not in merged_output_ids:
                merged_output_ids.append(new_output.id)

        # Resolve the (args_id, value=index) position row. We always create —
        # saved rows would have come back via position ids already; the
        # unified UI never re-uses positions.
        new_position = await create_arg_position(
            conn,
            args_id=resolved_arg_id,
            value=index,
            redis=redis,
        )
        if new_position.id not in merged_pos_ids:
            merged_pos_ids.append(new_position.id)

    return merged_arg_ids, merged_output_ids, merged_pos_ids
