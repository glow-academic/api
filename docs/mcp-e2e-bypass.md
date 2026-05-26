# Hand-off: extend the E2E auth bypass to the MCP middleware

## Problem
`/mcp/` (JSON-RPC: `tools/list`, `tools/call`) returns **401** for the same
`Authorization: Bearer <E2E_BYPASS_TOKEN>` + `X-E2E-Profile-Id` that the resource
endpoints (`/persona/search`, etc.) accept. So the CLI/E2E harness can drive
every resource endpoint but **cannot reach MCP** — `glow mcp list-tools` → 401.

Repro (api running with `E2E_BYPASS_TOKEN` set):
```bash
export GLOW_INSTANCE_URL=http://localhost:8000
export GLOW_TOKEN=<E2E_BYPASS_TOKEN>
export GLOW_E2E_PROFILE_ID=<seed superadmin profile uuid>
glow personas search     # ✅ works (bypass honored)
glow mcp list-tools      # ❌ "MCP request failed (HTTP 401 Unauthorized)"
```

## Root cause
`/mcp/` is a **separate FastMCP sub-app** guarded by its own middleware,
`McpOAuthMiddleware` (`core/app/infra/mcp/oauth.py`). Its `dispatch()` does **only**
Keycloak JWT verification:
```python
# core/app/infra/mcp/oauth.py  (~line 223-244)
token  = extract_bearer_token(request.headers.get("authorization"))
claims = verify_jwt(token)                 # ← E2E_BYPASS_TOKEN is not a JWT → ValueError → 401
profile_id = await _resolve_profile_id(claims, pool)
```
It never runs the **E2E bypass**, which lives in a *different* middleware:
`core/app/infra/identity/middleware.py` (~line 162-205). That bypass is env-gated
(`E2E_BYPASS_TOKEN`), constant-time-compares the bearer token, resolves the profile
from `X-E2E-Profile-Id` (or `E2E_BYPASS_PROFILE_ID`), validates it exists, and sets
`request.state.profile_id`. The MCP sub-app's middleware chain doesn't include it.

This is **not** a token/JWT mismatch to "fix" on the client — it's that the bypass
simply isn't wired into the MCP path. Same mechanism, missing in one place.

## Fix — factor the bypass into a shared helper, call it from both middlewares
Single source of truth, single prod-safety gate (`E2E_BYPASS_TOKEN` unset ⇒ no-op
everywhere). Lift the existing block out of `identity/middleware.py` verbatim:

```python
# core/app/infra/identity/e2e_bypass.py  (new)
import hmac
from uuid import UUID
from fastapi import HTTPException
from app.infra.identity.resolve_identity import Identity, extract_bearer_token
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.sessions...  import get_or_create_session   # same import middleware.py uses
from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.middleware import (
    _E2E_BYPASS_ENABLED, _E2E_BYPASS_TOKEN, _E2E_DEFAULT_PROFILE_ID,
)  # or move these consts into this module and import them back into middleware.py

async def try_e2e_bypass(request) -> Identity | None:
    """If the env-gated E2E bypass applies to this request, resolve the
    impersonated profile, set request.state, and return its Identity.
    Returns None when the bypass is disabled or the token doesn't match
    (caller then proceeds with normal JWT auth)."""
    auth = request.headers.get("authorization")
    token = extract_bearer_token(auth)
    if not (_E2E_BYPASS_ENABLED and token and
            hmac.compare_digest(token, _E2E_BYPASS_TOKEN)):
        return None

    header_profile = request.headers.get("X-E2E-Profile-Id", "").strip()
    if header_profile:
        try:
            profile_id = UUID(header_profile)
        except ValueError as e:
            raise HTTPException(401, f"E2E bypass: invalid X-E2E-Profile-Id ({header_profile!r})") from e
    elif _E2E_DEFAULT_PROFILE_ID is not None:
        profile_id = _E2E_DEFAULT_PROFILE_ID
    else:
        raise HTTPException(401, "E2E bypass: no profile to impersonate. Set E2E_BYPASS_PROFILE_ID or send X-E2E-Profile-Id.")

    pool, redis = get_pool(), get_redis_client()
    ctx = await resolve_profile_identity_context(pool, profile_id, redis)
    if ctx is None:
        raise HTTPException(401, f"E2E bypass: profile {profile_id} not found in DB.")
    async with pool.acquire() as conn:
        session_id = await get_or_create_session(conn, profile_id)
    identity = Identity(profile_id=profile_id, session_id=session_id,
                        email=ctx.primary_email, role=ctx.role)
    request.state.profile_id = str(profile_id)
    request.state.session_id = str(session_id)
    request.state.identity = identity
    return identity
```

**1. `identity/middleware.py`** — replace the inline block (~162-205) with:
```python
identity = await try_e2e_bypass(request)
if identity is not None:
    return identity
```

**2. `mcp/oauth.py` `McpOAuthMiddleware.dispatch`** — right after the token is
extracted (~line 223), before `verify_jwt`:
```python
from app.infra.identity.e2e_bypass import try_e2e_bypass
if await try_e2e_bypass(request) is not None:   # sets request.state.profile_id
    return await call_next(request)
```
(`get_mcp_profile_id` already reads `request.state.profile_id`, so no downstream
changes are needed.)

## Why this approach
- **Reuses the exact bypass we already trust** — no JWT, no new auth surface.
- **One prod-safety gate**: `E2E_BYPASS_TOKEN` unset (prod) ⇒ `try_e2e_bypass`
  returns `None` everywhere ⇒ MCP still requires a real Keycloak JWT in prod.
- **DRY**: bypass logic lives in one file instead of being duplicated.

## Verify
After the change (api running with `E2E_BYPASS_TOKEN` set):
```bash
glow mcp list-tools                                  # ✅ real tool list
glow mcp call <tool> --args '{...}'                  # ✅ real result
```
Then the docs `mcp-overview`, `mcp-list-tools`, `mcp-call` VHS clips can be recorded
with the same bypass as every other CLI clip.
