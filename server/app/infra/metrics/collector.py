"""Metrics collector for FastAPI application metrics (Redis-backed for multi-instance)."""

import time
from collections import deque
from datetime import UTC
from typing import Any

import asyncpg  # type: ignore
import psutil  # type: ignore

# In-memory metrics storage (fallback when Redis unavailable)
_requests_count = 0
_errors_count = 0
_latency_samples: deque[float] = deque(maxlen=1000)  # Keep last 1000 samples
_db_pool: asyncpg.Pool | None = None
_redis_client: Any | None = None


async def initialize_metrics(
    db_pool: asyncpg.Pool, redis_client: Any | None = None
) -> None:
    """Initialize metrics collector with database pool and Redis client.

    Args:
        db_pool: Database connection pool for writing snapshots
        redis_client: Redis client for shared metrics (optional, falls back to in-memory)
    """
    global _db_pool, _redis_client
    _db_pool = db_pool
    _redis_client = redis_client

    # Initialize Redis counters if Redis available
    if _redis_client:
        from app.utils.logging.db_logger import get_logger

        logger = get_logger("app.infra.metrics.collector")
        try:
            # Initialize counters to 0 if they don't exist (async Redis client)
            await _redis_client.set("metrics:requests_total", 0, nx=True)
            await _redis_client.set("metrics:errors_total", 0, nx=True)
            logger.info("Metrics collector initialized with Redis backend")
        except Exception as e:
            logger.warning(
                f"Failed to initialize Redis metrics: {e}, using in-memory fallback"
            )
            _redis_client = None
    else:
        from app.utils.logging.db_logger import get_logger

        logger = get_logger("app.infra.metrics.collector")
        logger.info(
            "Metrics collector initialized with in-memory backend (Redis unavailable)"
        )


async def record_request(latency_ms: float) -> None:
    """Record a successful request with its latency.

    Args:
        latency_ms: Request latency in milliseconds
    """
    global _requests_count

    if _redis_client:
        try:
            # Atomic increment in Redis
            await _redis_client.incr("metrics:requests_total")

            # Store latency sample in Redis list (per-minute bucket)
            now = time.time()
            minute_timestamp = int(now // 60) * 60
            latency_key = f"metrics:latency:{minute_timestamp}"

            await _redis_client.lpush(latency_key, str(latency_ms))
            # Set TTL to 2 minutes (expires after snapshot)
            await _redis_client.expire(latency_key, 120)
        except Exception:
            # Fallback to in-memory if Redis fails
            _requests_count += 1
            _latency_samples.append(latency_ms)
    else:
        # In-memory fallback
        _requests_count += 1
        _latency_samples.append(latency_ms)


async def record_error() -> None:
    """Record an error."""
    global _errors_count

    if _redis_client:
        try:
            # Atomic increment in Redis
            await _redis_client.incr("metrics:errors_total")
        except Exception:
            # Fallback to in-memory if Redis fails
            _errors_count += 1
    else:
        # In-memory fallback
        _errors_count += 1


async def log_metrics_snapshot() -> None:
    """Log metrics snapshot to database (no leader election).

    This function is called by the notify service endpoint.
    No leader election needed since notify service is single instance.
    """
    if _db_pool is None:
        return

    # Read metrics from Redis or in-memory
    requests_total = 0
    errors_total = 0
    avg_latency_ms = 0.0

    if _redis_client:
        try:
            # Read counters from Redis
            requests_str = await _redis_client.get("metrics:requests_total")
            errors_str = await _redis_client.get("metrics:errors_total")

            requests_total = int(requests_str) if requests_str else 0
            errors_total = int(errors_str) if errors_str else 0

            # Read latency samples from Redis
            now = time.time()
            minute_timestamp = int(now // 60) * 60
            latency_key = f"metrics:latency:{minute_timestamp}"

            latency_samples = await _redis_client.lrange(latency_key, 0, -1)
            if latency_samples:
                latencies = [
                    float(s.decode() if isinstance(s, bytes) else s)
                    for s in latency_samples
                ]
                avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0
        except Exception as e:
            from app.utils.logging.db_logger import get_logger

            logger = get_logger("app.infra.metrics.collector")
            logger.warning(f"Error reading from Redis, using in-memory fallback: {e}")
            # Fallback to in-memory
            requests_total = _requests_count
            errors_total = _errors_count
            if _latency_samples:
                avg_latency_ms = sum(_latency_samples) / len(_latency_samples)
    else:
        # In-memory fallback
        requests_total = _requests_count
        errors_total = _errors_count
        if _latency_samples:
            avg_latency_ms = sum(_latency_samples) / len(_latency_samples)

    # Get system metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory_info = psutil.Process().memory_info()
    memory_bytes = memory_info.rss

    # Round timestamp to minute
    now = time.time()
    rounded_minute = int(now // 60) * 60
    from datetime import datetime

    ts = datetime.fromtimestamp(rounded_minute, tz=UTC)

    # Write to database
    from app.infra.metrics_snapshot import write_metrics_snapshot

    await write_metrics_snapshot(
        _db_pool,
        ts=ts,
        requests_total=requests_total,
        errors_total=errors_total,
        avg_latency_ms=avg_latency_ms,
        cpu_percent=cpu_percent,
        memory_bytes=memory_bytes,
    )


async def log_health_checks() -> None:
    """Log health checks to database (no leader election).

    This function is called by the health endpoint.
    No leader election needed since notify service is single instance.
    """
    if _db_pool is None:
        return

    try:
        from app.infra.health.checks import run_service_checks

        checks = await run_service_checks()

        # Round timestamp to minute
        now = time.time()
        rounded_minute = int(now // 60) * 60
        from datetime import datetime

        ts = datetime.fromtimestamp(rounded_minute, tz=UTC)

        # Write to database
        from app.infra.metrics_snapshot import write_health_checks

        await write_health_checks(_db_pool, ts=ts, checks=checks)
    except Exception as e:
        # Log error but don't break health endpoint
        from app.utils.logging.db_logger import get_logger

        logger = get_logger("app.infra.metrics.collector")
        logger.warning(f"Error logging health checks: {e}")


async def get_current_metrics() -> dict[str, Any]:
    """Get current metrics snapshot (for debugging/monitoring).

    Returns:
        Dictionary with current metrics values
    """
    if _redis_client:
        try:
            requests_str = await _redis_client.get("metrics:requests_total")
            errors_str = await _redis_client.get("metrics:errors_total")

            requests_total = int(requests_str) if requests_str else 0
            errors_total = int(errors_str) if errors_str else 0

            # Get latency samples from current minute
            now = time.time()
            minute_timestamp = int(now // 60) * 60
            latency_key = f"metrics:latency:{minute_timestamp}"
            latency_samples = await _redis_client.lrange(latency_key, 0, -1)

            avg_latency_ms = 0.0
            sample_count = 0
            if latency_samples:
                latencies = [
                    float(s.decode() if isinstance(s, bytes) else s)
                    for s in latency_samples
                ]
                avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0
                sample_count = len(latencies)

            return {
                "requests_total": requests_total,
                "errors_total": errors_total,
                "avg_latency_ms": avg_latency_ms,
                "sample_count": sample_count,
                "backend": "redis",
            }
        except Exception:
            # Fallback to in-memory
            pass

    # In-memory fallback
    avg_latency_ms = 0.0
    if _latency_samples:
        avg_latency_ms = sum(_latency_samples) / len(_latency_samples)

    return {
        "requests_total": _requests_count,
        "errors_total": _errors_count,
        "avg_latency_ms": avg_latency_ms,
        "sample_count": len(_latency_samples),
        "backend": "memory",
    }
