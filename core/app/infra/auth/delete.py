"""Auth delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.auth.permissions import compute_can_delete
from app.infra.auth.permissions_context import resolve_auth_permissions_context
from app.infra.auth.refresh import refresh_auth_impl
from app.infra.auth.types import DeleteAuthApiResponse, DeleteAuthResult
from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.auth.delete import delete_auths
from app.tools.artifacts.auth.get import get_auths
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.names.get import get_names
from app.utils.logging.db_logger import get_logger
from app.utils.cache.hedged_row import transaction_with_writeback

logger = get_logger(__name__)

ARTIFACT = "auth"

# Appended to a delete result's message when the post-delete Keycloak sync did
# not complete. Delete semantics differ from create/update: the DB row IS
# deleted, but the identity provider may still exist in Keycloak (stale IdP),
# so the provider was likely NOT de-provisioned there.
_KEYCLOAK_DELETE_SYNC_WARNING = (
    " (warning: identity-provider de-provisioning sync to Keycloak did not "
    "complete — the provider may still exist in Keycloak until it is reachable "
    "and re-syncs)"
)


async def delete_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    ids: list[UUID] | None = None,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    # All-matching path (additive — explicit-ids path stays untouched).
    all: bool = False,
    excluded_ids: list[UUID] | None = None,
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
) -> DeleteAuthApiResponse:
    """Auth bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_auth_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``ids``
        needed, the dormant deletion is located by the operation key.
    """
    from app.infra.identity.keycloak_sync import perform_keycloak_sync

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above perm checks so ack/all paths don't trip on the
    # original "iterate ``ids`` and 404" loop (``ids`` is None on ack).
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "delete":
            raise HTTPException(
                status_code=404,
                detail="No pending auth delete for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            pass
        else:
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await restore_artifacts(
                        conn, table="auth_artifact", ids=[target_id],
                    )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="delete",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_auth_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        try:
            sync_result = await perform_keycloak_sync(department_id=None)
        except Exception as e:  # defensive — perform_* shouldn't raise
            logger.warning(f"Keycloak sync errored after auth delete ack: {e}")
            sync_result = None
        ack_message = "Delete confirmed" if accept else "Delete rejected — auth restored"
        # Only an accepted delete de-provisions the IdP; a reject restores the
        # row, so the de-provision warning is irrelevant there.
        if accept and (sync_result is None or not sync_result.success):
            detail = sync_result.message if sync_result else "Keycloak sync errored"
            logger.warning(
                f"Keycloak sync did not complete after auth delete ack: {detail}"
            )
            ack_message += _KEYCLOAK_DELETE_SYNC_WARNING
        return DeleteAuthApiResponse(
            results=[
                DeleteAuthResult(
                    success=True,
                    auth_id=target_id,
                    message=ack_message,
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids server-side ────────────────────
    if all:
        from app.infra.auth.resolve_matching_ids import resolve_matching_auth_ids
        matching = await resolve_matching_auth_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_department_ids=filter_department_ids,
            department_search=department_search,
            flag_search=flag_search,
        )
        excluded = set(excluded_ids or [])
        ids = [aid for aid in matching if aid not in excluded]

    # ── First-call requirements ───────────────────────────────────────
    if not ids:
        if all:
            return DeleteAuthApiResponse(results=[], idempotency_key=idempotency_key)
        raise HTTPException(
            status_code=400,
            detail="`auth_ids` is required for first-call deletion "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with filter fields).",
        )

    # ── Profile context ───────────────────────────────────────────────
    with timed("profile"):
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

    # ── Per-item permission checks ────────────────────────────────────
    # Explicit-ids path fails fast (preserves existing 404/403 behavior).
    # All-matching path soft-skips: collects per-row results so the
    # toast can say "X deleted, Y skipped (no permission)" without
    # aborting rows the user CAN delete.
    skipped_results: list[DeleteAuthResult] = []
    permitted_ids: list[UUID] = []

    with timed("permissions"):
     async with pool.acquire() as conn:
        for idx, auth_id in enumerate(ids):
            ctx = await resolve_auth_permissions_context(conn, auth_id)
            if not ctx.exists:
                if all:
                    skipped_results.append(DeleteAuthResult(
                        success=False, auth_id=auth_id,
                        message=f"Auth {auth_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Auth {auth_id} not found.",
                )
            if not compute_can_delete(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                active_settings_count=ctx.active_settings_count,
            ):
                if all:
                    skipped_results.append(DeleteAuthResult(
                        success=False, auth_id=auth_id,
                        message=f"No permission to delete auth {auth_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this auth entry.",
                )
            permitted_ids.append(auth_id)

    if all:
        ids = permitted_ids
        if not ids:
            return DeleteAuthApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Fetch names for result messages ───────────────────────────────
    name_map: dict[UUID, str] = {}
    with timed("names"):
     async with pool.acquire() as conn:
        artifacts = await get_auths(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(pool, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # ── Single transaction — bulk delete ──────────────────────────────
    with timed("db_write"):
     async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            result = await delete_auths(conn, ids, soft=soft)

            if soft and idempotency_key is not None:
                for aid in result.deleted_ids:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="delete",
                        artifact_id=aid,
                    )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    with timed("refresh"):
        await refresh_auth_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
        )

    # De-provision the deleted auth providers' Keycloak IdPs. The DB rows are
    # already committed; a failure here leaves stale IdP config in Keycloak
    # (the provider was NOT de-provisioned), so it must be surfaced, not
    # swallowed. ``perform_keycloak_sync`` does NOT raise on failure — it
    # returns ``KeycloakSyncResult(success=False)`` and logs internally, so
    # the old ``except Exception`` was dead code. Mirrors #249, adapted for
    # delete semantics. Soft deletes (pending confirmation) don't sync.
    keycloak_sync_failed = False
    if not soft:
        try:
            sync_result = await perform_keycloak_sync(department_id=None)
        except Exception as e:  # defensive — perform_* shouldn't raise
            logger.warning(f"Keycloak sync errored after auth delete: {e}")
            sync_result = None
        if sync_result is None or not sync_result.success:
            keycloak_sync_failed = True
            detail = sync_result.message if sync_result else "Keycloak sync errored"
            logger.warning(
                f"Keycloak sync did not complete after auth delete: {detail}"
            )

    results = [
        DeleteAuthResult(
            success=True,
            auth_id=pid,
            message=(
                f"Auth '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Auth '{name_map.get(pid, 'Unknown')}' deleted successfully"
            )
            + (_KEYCLOAK_DELETE_SYNC_WARNING if keycloak_sync_failed else ""),
        )
        for pid in result.deleted_ids
    ]

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeleteAuthApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
