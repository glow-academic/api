"""Invocation draft logic for the canonical test-owned invocation surface."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.invocation.types import (
    DraftFormState,
    PatchInvocationDraftApiRequest,
    PatchInvocationDraftApiResponse,
    SaveInvocationFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.invocation_drafts.create import create_invocation_draft
from app.tools.entries.invocation_drafts.refresh import refresh_invocation_drafts
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def _resolve_creatable_values(
    conn: asyncpg.Connection,
    redis: Redis,
    request: PatchInvocationDraftApiRequest,
) -> list[SaveInvocationFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place)."""

    errors: list[SaveInvocationFieldError] = []

    if request.name is not None and request.name_id is None:
        results = await search_names(
            conn,
            redis,
            search=request.name,
            limit_count=20,
            draft_id=request.draft_id,
        )
        needle = request.name.strip().lower()
        match = next(
            (
                item for item in results
                if isinstance(item.name, str) and item.name.strip().lower() == needle
            ),
            None,
        )
        request.name_id = match.id if match and match.id else (await create_name(conn, request.name, redis)).id

    if request.description is not None and request.description_id is None:
        results = await search_descriptions(
            conn,
            redis,
            search=request.description,
            limit_count=20,
            draft_id=request.draft_id,
        )
        needle = request.description.strip().lower()
        match = next(
            (
                item for item in results
                if isinstance(item.description, str)
                and item.description.strip().lower() == needle
            ),
            None,
        )
        request.description_id = (
            match.id
            if match and match.id
            else (await create_description(conn, request.description, redis)).id
        )

    return errors


async def patch_invocation_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchInvocationDraftApiRequest,
) -> PatchInvocationDraftApiResponse:
    """Patch the invocation draft and return server-authored form state."""

    request.draft_id = request.draft_id or request.input_draft_id
    request.input_draft_id = request.input_draft_id or request.draft_id

    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if request.idempotency_key is not None:
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_invocation_draft(
                    conn,
                    session_id=session_id,
                    id=request.idempotency_key,
                    soft=not request.accept,
                    profile_ids=[profile.profiles_id],
                    pending_ids=set(request.pending_ids or []),
                )
        async with pool.acquire() as conn:
            await refresh_invocation_drafts(conn)
        return PatchInvocationDraftApiResponse(
            success=True,
            draft_id=result.id,
            idempotency_key=request.idempotency_key,
            message="Draft accepted" if request.accept else "Draft rejected",
            form_state=DraftFormState(pending_ids=request.pending_ids or []),
        )

    async with pool.acquire() as conn:
        errors = await _resolve_creatable_values(conn, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[error.model_dump() for error in errors],
        )

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_invocation_draft(
                conn,
                session_id=session_id,
                id=request.draft_id,
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                value_id=request.value_id,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                key_ids=[request.key_id] if request.key_id else None,
                endpoint_ids=[request.endpoint_id] if request.endpoint_id else None,
                temperature_level_ids=[request.temperature_level_id] if request.temperature_level_id else None,
                pricing_ids=[request.pricing_id] if request.pricing_id else None,
                reasoning_level_ids=[request.reasoning_level_id] if request.reasoning_level_id else None,
                voice_ids=request.voice_ids,
                profile_ids=[profile.profiles_id],
                pending_ids=set(request.pending_ids or []),
            )

    async with pool.acquire() as conn:
        await refresh_invocation_drafts(conn)

    await invalidate_tags(["benchmark", "drafts"], redis=redis)

    return PatchInvocationDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=request.idempotency_key,
        message="Draft created successfully",
        form_state=DraftFormState(
            name_id=request.name_id,
            name=request.name,
            description_id=request.description_id,
            description=request.description,
            value_id=request.value_id,
            flag_ids=request.flag_ids or [],
            department_ids=request.department_ids or [],
            key_id=request.key_id,
            endpoint_id=request.endpoint_id,
            modality_ids=request.modality_ids or [],
            temperature_level_id=request.temperature_level_id,
            pricing_id=request.pricing_id,
            reasoning_level_id=request.reasoning_level_id,
            quality_ids=request.quality_ids or [],
            voice_ids=request.voice_ids or [],
            pending_ids=request.pending_ids or [],
        ),
    )
