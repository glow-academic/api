"""Docs MCP proxy — forward requests to the Glow docs sibling.

Signs a short-lived JWT with the Glow API's key so the docs instance
can verify it against the Glow API's /jwks endpoint.

Protected by McpOAuthMiddleware (same as /mcp).
"""

import os
import time

import httpx
import jwt
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.infra.identity.jwks import get_key_id, get_private_key
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

DEPLOYMENT_ID = os.getenv("DEPLOYMENT_ID") or os.getenv("COMPOSE_PROJECT_NAME") or ""
ORIGIN = os.getenv("ORIGIN", "http://localhost:8000")
_TIMEOUT = 30.0

router = APIRouter(tags=["docs-proxy"])


def _sign_docs_token(email: str = "", name: str = "") -> str:
    """Sign a short-lived JWT with the Glow API's key for the docs instance."""
    private_key = get_private_key()
    kid = get_key_id()
    now = int(time.time())
    payload = {
        "sub": email,
        "name": name,
        "iss": ORIGIN,
        "iat": now,
        "exp": now + 300,  # 5 minutes
        "type": "docs_proxy",
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


@router.post("/docs-mcp")
async def docs_mcp_proxy(request: Request):
    """Forward an MCP request to the Glow docs sibling.

    This route is behind McpOAuthMiddleware, so the user is already
    authenticated. We re-sign with the Glow API's key so the docs
    can verify against our /jwks.
    """
    # Extract user info from the authenticated request
    email = getattr(request.state, "mcp_proxy_sub", "") or ""
    name = getattr(request.state, "mcp_proxy_name", "") or ""

    # If not a proxy request, try to get from profile
    if not email and hasattr(request.state, "profile_id"):
        email = "authenticated"

    # Sign a Glow API token for the docs
    token = _sign_docs_token(email=email, name=name)

    body = await request.body()

    # Find docs container on the shared network
    # Docs container follows: {docs_deployment_id}-nginx
    # On the shared glow-{deployment_id} network, it's also reachable
    # as the docs nginx container name
    # glow-docs is the network alias for the docs nginx on the shared deployment network
    urls = [
        "http://glow-docs:80/api/mcp",
    ]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    resp = None
    for url in urls:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, content=body, headers=headers)
            break
        except (httpx.ConnectError, httpx.TimeoutException):
            logger.warning(f"Docs proxy: failed to connect to {url}")
            continue

    if resp is None:
        return Response(
            content='{"error": "Could not reach docs instance"}',
            status_code=502,
            media_type="application/json",
        )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )
