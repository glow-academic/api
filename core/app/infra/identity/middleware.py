"""Unified auth middleware — resolves identity on every request.

Validates JWT (Authorization: Bearer), then sets:
  - request.state.profile_id
  - request.state.session_id
  - request.state.identity

group_id and run_id are NOT resolved here — they are stateless and
derived by each infra function from the entity being operated on
(e.g., invocation_id → test → call → run → group).

Uses FastAPI security utilities so the OpenAPI spec includes proper
securitySchemes (http/bearer) on every protected endpoint.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.infra.globals import get_pool
from app.infra.identity.resolve_identity import (
    Identity,
    resolve_identity,
)
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

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

    SSE callers that can't set headers (browser ``EventSource``) must
    proxy through the client's BFF route at ``/api/stream/{artifact}``,
    which attaches the Bearer header server-side. We deliberately do
    NOT accept a ``?token=`` query fallback — that would leak the JWT
    through server logs, browser history, and Referer headers.

    Sets on request.state:
      - profile_id: UUID
      - session_id: UUID
      - identity: full Identity object

    Raises:
        HTTPException 401 if auth is missing or invalid
    """
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

    request.state.profile_id = str(identity.profile_id)
    request.state.session_id = str(identity.session_id)
    request.state.identity = identity

    return identity
