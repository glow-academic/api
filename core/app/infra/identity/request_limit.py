"""Per-profile request-rate enforcement (RL1 / RL2 / SEC3).

A role's ``request_limit`` (the seeded ``daily-10`` and friends) is resolved all
the way onto :class:`ProfileIdentityContext` — but until this it was enforced
NOWHERE. The limit *read* as enforced (seeded, role-attached, surfaced in the
profile UI) while a holder could call the expensive LLM ``generate`` path
unbounded (RL1), which also left the costly provider calls with no quota at all
(RL2 / report-5 SEC3 — unmetered LLM cost for the price of a fresh UUID).

This wires the already-plumbed ``request_limit`` to a real check at the
generation entry points (which already hold the resolved identity, so no
re-resolve / threading). It uses a fixed-window Redis counter — the same
INCR + EXPIRE pattern used elsewhere in the codebase (e.g.
``increment_guest_count`` / ``set_active_connection``).
"""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException
from redis.asyncio import Redis

# interval string ("1 day", "30 minutes", "1 hour", …) → window seconds.
_UNIT_SECONDS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
    "week": 604800,
}
_DEFAULT_WINDOW = 86400  # 1 day — matches the seeded ``daily-10`` limit.


def interval_to_seconds(interval: str | None) -> int:
    """Parse a ``request_limit_interval`` string to a window in seconds.

    Accepts ``"1 day"``, ``"30 minutes"``, ``"hour"`` (qty defaults to 1), etc.
    Falls back to one day for anything unrecognized so a malformed interval
    never disables the limit nor crashes the hot path.
    """
    if not interval:
        return _DEFAULT_WINDOW
    m = re.match(r"\s*(\d+)?\s*([a-zA-Z]+)", interval.strip().lower())
    if not m:
        return _DEFAULT_WINDOW
    qty = int(m.group(1)) if m.group(1) else 1
    unit = m.group(2).rstrip("s")  # "days" → "day"
    return qty * _UNIT_SECONDS.get(unit, _DEFAULT_WINDOW)


async def enforce_request_limit(
    redis: Redis,
    *,
    profile_id: UUID,
    request_limit: int | None,
    request_limit_interval: str | None,
    operation: str,
) -> None:
    """Reject (HTTP 429) when ``profile_id`` has exceeded ``request_limit``
    metered ``operation`` calls within ``request_limit_interval``.

    - No-op when ``request_limit`` is ``None``/``<= 0`` — roles without a quota
      (e.g. superadmin) are unlimited by design.
    - Fixed window via Redis ``INCR`` + ``EXPIRE``-on-first-hit: the window
      resets ``interval`` seconds after the first call within it.
    - Fail-OPEN on a Redis error: a counter outage must never block legitimate
      generation (this is a cost/abuse guard, not an auth gate).
    """
    if not request_limit or request_limit <= 0:
        return

    window = interval_to_seconds(request_limit_interval)
    key = f"reqlimit:{profile_id}:{operation}"
    try:
        count = await redis.incr(key)
        if count == 1:
            # First call in this window — start the TTL so it self-resets.
            await redis.expire(key, window)
    except Exception:
        return  # fail-open: don't break generation on a Redis hiccup

    if count > request_limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Request limit reached "
                f"({request_limit} per {request_limit_interval or '1 day'}). "
                "Please try again later."
            ),
            headers={"Retry-After": str(window)},
        )
