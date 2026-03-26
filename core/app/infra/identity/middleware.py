"""Unified auth middleware — replaces get_profile_id + get_session_id dependencies.

Validates JWT (Authorization: Bearer) on every request, then sets
request.state.profile_id and request.state.session_id.

The client no longer needs to send X-Profile-Id or X-Session-Id headers.

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

    # 2. Set on request.state (backward-compatible with existing code)
    request.state.profile_id = str(identity.profile_id)
    request.state.session_id = str(identity.session_id)
    request.state.identity = identity

    return identity
