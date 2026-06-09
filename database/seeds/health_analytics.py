"""Analytical seed — service health + application metrics history.

Populates recent hours of ``health_entry`` (per monitored service) and
``metrics_entry`` (app-wide samples) so the Health dashboard
(the ``health-overview`` + ``health-status-indicators`` demos) renders
real service-uptime cards and a populated "Application Metrics" panel on
first load — instead of an empty dashed box from ``total_count: 0`` with
empty ``service_hourly`` / ``metrics_hourly``.

Root cause this fixes: ``/system/health`` is backed by ``health_mv`` and
``metrics_mv``, which aggregate the ``health_entry`` / ``metrics_entry``
tables. Those tables are populated at runtime by the health collector;
a freshly-seeded template has no collector history, so the MVs are empty
and the dashboard renders blank. The data is *seedable* (plain entry
rows), so we backfill synthetic history here — mirroring how
``attempts_analytics`` / ``tests_analytics`` enrich the other dashboards.

**Canonical-only**: uses ONLY the black-box create helpers in
``app/tools/entries/{sessions,health,metrics}/create.py``. No inline SQL.
Time is distributed through the helpers' ``ts`` arguments. The runner
refreshes ``health_mv`` + ``metrics_mv`` AFTER this seed runs (Phase 3 —
analytical seeds), so the search black-boxes the dashboard calls return
the freshly-aggregated buckets.

Determinism: a single deterministic session id via
``sid("health-analytics/session")`` carries every row, and each health
row uses a deterministic id, so replays short-circuit on the unique PK.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.health.create import create_health
from app.tools.entries.metrics.create import create_metrics_entry_internal
from app.tools.entries.sessions.create import create_session
from database.seeds.ids import sid

# ``health_mv`` only aggregates these services (see the MV's WHERE clause:
# service = ANY(ARRAY['websocket','redis','tus','database','keycloak'])).
# Rows for any other service name are invisible to the dashboard.
_SERVICES = ("websocket", "redis", "tus", "database", "keycloak")

# Hours of rolling history. The dashboard's default page_limit is 168
# (7 days of hourly buckets); 72 gives three full days of trend without
# bloating the template.
_HOURS = 72

# Checks per service per hour — >1 so ``uptime_percent`` is a real ratio
# and the occasional injected failure renders as a sub-100% / degraded
# status indicator.
_CHECKS_PER_HOUR = 4

# Per-service (baseline latency ms, failure cadence). A non-zero cadence N
# fails every Nth check, so the status-indicator demo shows a realistic
# mix of fully-healthy services and a couple of intermittently-degraded
# ones rather than a uniform 100%-green wall.
_SERVICE_PROFILE: dict[str, tuple[float, int]] = {
    "websocket": (18.0, 0),   # always healthy
    "redis": (3.0, 0),        # always healthy
    "database": (9.0, 0),     # always healthy
    "tus": (42.0, 53),        # a rare failed upload-probe
    "keycloak": (65.0, 29),   # intermittent auth-probe failures -> degraded
}


def _anchor() -> datetime:
    """Most-recent whole hour in UTC — the top of the rolling window."""
    return datetime.now(UTC).replace(minute=0, second=0, microsecond=0)


async def seed(pool: asyncpg.Pool, redis: Redis) -> int:
    """Insert service-health + app-metrics history. Returns rows created.

    No FK discovery is needed: health/metrics are platform-level signals,
    not setup-scoped — every setup's Health dashboard benefits, exactly
    like the runtime collector would populate them.
    """
    anchor = _anchor()
    inserted = 0
    async with pool.acquire() as conn:
        # One shared, profile-less collector session carries every row.
        session_id = sid("health-analytics/session")
        try:
            await create_session(
                conn,
                redis,
                id=session_id,
                created_at=anchor - timedelta(hours=_HOURS),
            )
        except asyncpg.UniqueViolationError:
            pass

        for hour in range(_HOURS):
            bucket = anchor - timedelta(hours=hour)

            # ── service health checks ───────────────────────────────
            for service in _SERVICES:
                base_latency, fail_period = _SERVICE_PROFILE[service]
                for check in range(_CHECKS_PER_HOUR):
                    seq = hour * _CHECKS_PER_HOUR + check
                    ok = fail_period == 0 or (seq % fail_period != 0)
                    latency = base_latency + ((seq * 7) % 25) + (
                        0.0 if ok else 180.0
                    )
                    ts = bucket + timedelta(
                        minutes=check * (60 // _CHECKS_PER_HOUR)
                    )
                    try:
                        await create_health(
                            conn,
                            redis,
                            service=service,
                            ok=ok,
                            latency_ms=round(latency, 2),
                            ts=ts,
                            error="" if ok else f"{service} health probe timed out",
                            session_id=session_id,
                            id=sid(f"health-analytics/{service}/{hour}/{check}"),
                        )
                        inserted += 1
                    except asyncpg.UniqueViolationError:
                        pass

            # ── application metrics sample (one per hour) ───────────
            try:
                await create_metrics_entry_internal(
                    conn,
                    redis,
                    ts=bucket,
                    requests_total=1000 + hour * 37,
                    errors_total=hour % 9,
                    avg_latency_ms=round(28.0 + ((hour * 13) % 40), 2),
                    cpu_percent=round(22.0 + ((hour * 5) % 35), 2),
                    memory_bytes=512 * 1024 * 1024 + (hour % 12) * 8 * 1024 * 1024,
                    session_id=session_id,
                )
                inserted += 1
            except asyncpg.UniqueViolationError:
                pass

    return inserted
