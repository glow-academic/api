"""Unified auth middleware — replaces get_profile_id + get_session_id dependencies.

Validates license key (X-Api-Key) and JWT (Authorization: Bearer) on every request,
then sets request.state.profile_id and request.state.session_id.

The client no longer needs to send X-Profile-Id or X-Session-Id headers.

Uses FastAPI security utilities so the OpenAPI spec includes proper
securitySchemes (apiKey + http/bearer) on every protected endpoint.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.infra.globals import get_pool
from app.infra.identity.license_key import validate_license_key
from app.infra.identity.resolve_identity import (
    Identity,
    resolve_identity,
)

logger = logging.getLogger(__name__)

# OpenAPI security schemes — these generate securitySchemes in the spec
_api_key_scheme = APIKeyHeader(
    name="X-Api-Key",
    scheme_name="LicenseKey",
    description="Organization license key (e.g. glw_sk_abc123). Required on every request.",
    auto_error=False,
)
_bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    description="Keycloak-issued JWT token. Resolves the caller's profile and session.",
    auto_error=False,
)


async def require_auth(
    request: Request,
    api_key: str | None = Depends(_api_key_scheme),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> Identity:
    """FastAPI dependency that validates auth and resolves identity.

    Requires:
      - X-Api-Key header (license key, always required)
      - Authorization: Bearer <jwt> (user identity, always required)

    Sets on request.state:
      - profile_id: UUID
      - session_id: UUID
      - identity: full Identity object

    Raises:
        HTTPException 401 if auth is missing or invalid
    """
    # 1. Validate license key
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Api-Key header",
        )

    license_info = await validate_license_key(api_key)
    if not license_info.valid:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid license key: {license_info.error}",
        )

    # 2. Validate JWT and resolve identity
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

    # 3. Set on request.state (backward-compatible with existing code)
    request.state.profile_id = str(identity.profile_id)
    request.state.session_id = str(identity.session_id)
    request.state.identity = identity

    return identity
