"""Unified auth middleware — resolves identity + context on every request.

Validates JWT (Authorization: Bearer), then sets:
  - request.state.profile_id
  - request.state.session_id
  - request.state.group_id (latest group for this session)
  - request.state.run_id (latest run in this group, if any)

The client no longer needs to send profile/session/group/run IDs.

Uses FastAPI security utilities so the OpenAPI spec includes proper
securitySchemes (http/bearer) on every protected endpoint.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.infra.globals import get_pool
from app.infra.identity.resolve_identity import (
    Identity,
    resolve_identity,
)

logger = logging.getLogger(__name__)

# OpenAPI security scheme — generates securitySchemes in the spec
_bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    description="Keycloak-issued JWT token. Resolves the caller's profile and session.",
    auto_error=False,
)


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> Identity:
    """FastAPI dependency that validates auth and resolves identity.

    Requires:
      - Authorization: Bearer <jwt> (user identity, always required)

    Sets on request.state:
      - profile_id: UUID
      - session_id: UUID
      - group_id: UUID | None (latest group for this session)
      - run_id: UUID | None (latest run in this group)
      - identity: full Identity object

    Raises:
        HTTPException 401 if auth is missing or invalid
    """
    # 1. Validate JWT and resolve identity
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization: Bearer <token> header",
        )

    pool = get_pool()
    try:
        identity = await resolve_identity(credentials.credentials, pool)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    # 2. Resolve group + run context from session
    group_id = None
    run_id = None
    try:
        from app.tools.entries.groups.search import search_groups
        from app.tools.entries.runs.search import search_runs

        async with pool.acquire() as conn:
            groups = await search_groups(
                conn,
                session_ids=[identity.session_id],
                limit=1,
            )
            if groups:
                group_id = groups[0].id
                runs, _ = await search_runs(
                    conn,
                    group_ids=[group_id],
                    limit=1,
                )
                if runs:
                    run_id = runs[0].run_id
    except Exception as e:
        logger.warning(f"Failed to resolve group/run context: {e}")

    # 3. Set on request.state
    request.state.profile_id = str(identity.profile_id)
    request.state.session_id = str(identity.session_id)
    request.state.group_id = str(group_id) if group_id else None
    request.state.run_id = str(run_id) if run_id else None
    request.state.identity = identity

    return identity
