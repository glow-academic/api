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
from pydantic import BaseModel
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

# RL-B2 (report-18): INCR + EXPIRE as two separate round-trips is not atomic —
# the EXPIRE can be lost (Redis blip, cancellation, or a co-batched pipeline
# error), leaving a TTL-less key that 429s a profile FOREVER. The prior
# self-heal re-armed the TTL on a LATER read, but that set a fresh full window
# from the read moment → up to ~2x quota slide. This Lua does INCR then arms
# the TTL iff none is set, ATOMICALLY in one round-trip: the EXPIRE can never
# be lost (so no forever-429 and no read-time re-arm), and a live window is
# never extended (EXPIRE only fires when TTL < 0). Fixed-window, exactly once.
_INCR_EXPIRE_LUA = """
local c = redis.call('INCR', KEYS[1])
if redis.call('TTL', KEYS[1]) < 0 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return c
"""


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
        # Atomic INCR + arm-TTL-if-unset (RL-B2). ``eval`` is a passthrough op
        # on BatchedRedis (not coalesced), so this is one ordered round-trip,
        # independent of the batched-write path.
        count = await redis.eval(_INCR_EXPIRE_LUA, 1, key, window)
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


# RL-status (SEC3 read layer): reads the counter + its TTL in ONE passthrough
# round-trip without mutating it. ``eval`` is not coalesced on BatchedRedis (same
# as the enforce path), so this is a consistent snapshot. GET on a missing key
# returns false→None; TTL returns -2 (missing) / -1 (no expire) / >=0 (seconds
# left). Read-only by construction: checking status never consumes quota.
_PEEK_LUA = """
return {redis.call('GET', KEYS[1]), redis.call('TTL', KEYS[1])}
"""


class RequestLimitStatus(BaseModel):
    """A profile's current request-limit usage for one metered ``operation``.

    The unified "have I exceeded my limit?" read that mirrors what
    :func:`enforce_request_limit` enforces, so a UI can show remaining quota and
    a reset countdown without having to provoke a 429.
    """

    operation: str
    limit: int | None  # None ⇒ unlimited (no quota on this role)
    interval: str
    window_seconds: int
    used: int
    remaining: int | None  # None when unlimited
    exceeded: bool  # True ⇒ quota reached; the next metered call is rejected
    unlimited: bool
    reset_seconds: int | None  # seconds until the window resets (None if no live window)


async def get_request_limit_status(
    redis: Redis,
    *,
    profile_id: UUID,
    request_limit: int | None,
    request_limit_interval: str | None,
    operation: str = "generate",
) -> RequestLimitStatus:
    """Return the caller's :class:`RequestLimitStatus` for ``operation``.

    - Unlimited (``limit`` None/<=0) ⇒ ``unlimited=True``, ``exceeded=False``.
    - Fail-OPEN on a Redis error (mirrors :func:`enforce_request_limit`): a
      counter outage reports not-exceeded rather than falsely telling the UI it
      is blocked.
    - ``exceeded`` is ``used >= limit`` — i.e. the quota is spent and the next
      metered call would be the one :func:`enforce_request_limit` rejects.
    """
    window = interval_to_seconds(request_limit_interval)
    interval = request_limit_interval or "1 day"

    if not request_limit or request_limit <= 0:
        return RequestLimitStatus(
            operation=operation,
            limit=None,
            interval=interval,
            window_seconds=window,
            used=0,
            remaining=None,
            exceeded=False,
            unlimited=True,
            reset_seconds=None,
        )

    used = 0
    reset_seconds: int | None = None
    try:
        raw_count, raw_ttl = await redis.eval(
            _PEEK_LUA, 1, f"reqlimit:{profile_id}:{operation}"
        )
        used = int(raw_count) if raw_count is not None else 0
        reset_seconds = int(raw_ttl) if raw_ttl is not None and int(raw_ttl) > 0 else None
    except Exception:
        used = 0  # fail-open: don't tell the UI it's blocked on a Redis hiccup
        reset_seconds = None

    remaining = max(0, request_limit - used)
    return RequestLimitStatus(
        operation=operation,
        limit=request_limit,
        interval=interval,
        window_seconds=window,
        used=used,
        remaining=remaining,
        exceeded=remaining == 0,
        unlimited=False,
        reset_seconds=reset_seconds,
    )
