"""Health check utilities for system services."""

import os
import time
from dataclasses import dataclass
from typing import Any

import asyncpg  # type: ignore
import httpx  # type: ignore

from app.infra.globals import get_pool, get_redis_client, get_sio_instance


@dataclass
class ServiceCheckResult:
    """Result of a service health check."""

    ok: bool
    latency_ms: float
    error: str = ""


async def check_database(pool: asyncpg.Pool | None) -> ServiceCheckResult:
    """Check database connectivity with a simple SELECT query."""
    start = time.perf_counter()
    if pool is None:
        return ServiceCheckResult(False, 0.0, "no pool configured")

    try:
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        latency = (time.perf_counter() - start) * 1000
        return ServiceCheckResult(True, latency)
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ServiceCheckResult(False, latency, str(e))


async def check_redis(redis_client: Any | None) -> ServiceCheckResult:
    """Check Redis connectivity with a PING command."""
    start = time.perf_counter()
    if redis_client is None:
        return ServiceCheckResult(False, 0.0, "redis disabled or not configured")

    try:
        pong = await redis_client.ping()
        latency = (time.perf_counter() - start) * 1000
        if pong:
            return ServiceCheckResult(True, latency)
        return ServiceCheckResult(False, latency, "PING returned falsy")
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ServiceCheckResult(False, latency, str(e))


async def check_keycloak() -> ServiceCheckResult:
    """Check Keycloak availability via HTTP GET to .well-known endpoint."""
    start = time.perf_counter()
    app_prefix = os.getenv("APP_PREFIX", "")
    explicit_keycloak_url = os.getenv("KEYCLOAK_URL")

    if explicit_keycloak_url:
        keycloak_url = explicit_keycloak_url.rstrip("/")
    else:
        docker_env = os.getenv("DOCKER_ENV")
        keycloak_internal_url = os.getenv("KEYCLOAK_INTERNAL_URL")

        if keycloak_internal_url:
            base_url = keycloak_internal_url.rstrip("/")
        elif docker_env:
            base_url = "http://keycloak:8080"
        else:
            base_url = "http://localhost:8080"

        keycloak_url = f"{base_url}{app_prefix}/auth"

    realm = "master"
    well_known = f"{keycloak_url}/realms/{realm}/.well-known/openid-configuration"

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(well_known)
        latency = (time.perf_counter() - start) * 1000

        if r.status_code == 200:
            return ServiceCheckResult(True, latency)

        if r.status_code == 403:
            try:
                error_body = r.json()
                if error_body.get("error_description") == "HTTPS required":
                    return ServiceCheckResult(
                        True, latency, "HTTPS required (will be fixed by sync)"
                    )
            except Exception:
                pass

        return ServiceCheckResult(False, latency, f"status={r.status_code}")
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ServiceCheckResult(False, latency, str(e))


async def check_websocket() -> ServiceCheckResult:
    """Check WebSocket server instance health."""
    start = time.perf_counter()
    try:
        sio = get_sio_instance()
        if sio is None:
            return ServiceCheckResult(False, 0.0, "no sio instance")

        handlers = getattr(sio, "handlers", {})
        if not handlers:
            latency = (time.perf_counter() - start) * 1000
            return ServiceCheckResult(
                False, latency, "no websocket handlers registered"
            )

        latency = (time.perf_counter() - start) * 1000
        return ServiceCheckResult(True, latency)
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ServiceCheckResult(False, latency, str(e))


async def run_service_checks() -> dict[str, ServiceCheckResult]:
    """Run all service health checks and return results."""
    pool = get_pool()
    redis_client = get_redis_client()

    db = await check_database(pool)
    redis = await check_redis(redis_client)
    keycloak = await check_keycloak()
    websocket = await check_websocket()

    return {
        "database": db,
        "redis": redis,
        "keycloak": keycloak,
        "websocket": websocket,
    }
