"""Big cache — per-caller dedupe of composed responses (L3).

Companion to the small cache primitives (get_cached / set_cached) in this
package, but for a different job:

  small cache (L1)          big cache (L3)
  ─────────────────         ─────────────────────
  shares leaf data          dedupes composed responses
  keyed by resource+ids     keyed by caller+request shape
  long TTL (5-60 min)       short TTL (10-60s)
  busts on resource write   busts on TTL or coarse tag invalidation
  used inside get_X tools   used inside *_impl orchestrators

Mental model: small cache makes "everyone fetching the same name" cheap;
big cache makes "the same caller asking the same question twice in a row"
cheap. They compose — a big-cache miss falls through to the small-cache-
backed leaf reads, no duplication of work.

Adopt by wrapping any `*_impl` aggregator in app/infra/{X}/ that:
  - reads only (no mutations of state)
  - takes profile_id/entity_id/etc. as explicit kwargs
  - returns a Pydantic model

Example:

    async def page_context_persona_impl(pool, redis, *, profile_id, entity_id):
        return await get_or_build(
            redis=redis,
            key=big_cache_key("persona/page_context", {
                "profile_id": str(profile_id),
                "entity_id": str(entity_id) if entity_id else None,
            }),
            tags=["context", "persona", "artifacts"],
            ttl_s=DEFAULT_BIG_CACHE_TTL_S,
            response_model=PageContextResponse,
            builder=lambda: _do_page_context_persona(pool, redis, profile_id, entity_id),
        )
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel
from redis.asyncio import Redis

from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

# Default TTL for big-cache entries. 30s is the sweet spot:
#   - covers SSR generateMetadata + page render of the same request (~10ms)
#   - covers tab-switching and quick navigation (~seconds)
#   - covers socket reconnects and aggressive polling
#   - short enough that mutations not caught by tag invalidation surface fast
# Per-call override is supported for handlers that want different staleness.
DEFAULT_BIG_CACHE_TTL_S: int = 30

# Distinct prefix from the small cache keys (http:cache:) so it's obvious in
# Redis CLI inspection which is which.
_BIG_CACHE_PREFIX = "big:cache:"

T = TypeVar("T", bound=BaseModel)


def big_cache_key(orchestrator: str, params: dict[str, Any]) -> str:
    """Stable cache key for a `*_impl` orchestrator's params.

    Sorted-keys + sha256 → deterministic, collision-resistant, length-bounded.
    The `orchestrator` arg is a logical name (e.g. "persona/page_context") —
    distinct prefix per caller keeps debugging readable.
    """
    payload = json.dumps({"o": orchestrator, "p": params}, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"{_BIG_CACHE_PREFIX}{orchestrator}:{digest[:32]}"


async def get_or_build(
    *,
    redis: Redis | None,
    key: str,
    tags: list[str],
    ttl_s: int,
    response_model: type[T],
    builder: Callable[[], Awaitable[T]],
    bypass_cache: bool = False,
) -> T:
    """Big-cache wrapper: return cached response, else run builder + cache.

    Drop-in for any `*_impl` orchestrator. Falls back to a direct builder
    call if redis is unavailable, so dev/test flows that don't run Redis
    don't break.
    """
    if redis is None or bypass_cache:
        return await builder()

    cached = await get_cached(key, redis=redis)
    if cached is not None:
        try:
            return response_model.model_validate(cached)
        except Exception as e:
            # Stale entry shape (e.g. response_model changed since write).
            # Treat as a miss; rebuild and overwrite.
            logger.warning(
                f"big_cache: stale entry shape for key={key[:60]}..., "
                f"rebuilding ({type(e).__name__})"
            )

    result = await builder()
    await set_cached(
        key,
        result.model_dump(mode="json"),
        ttl_s,
        tags,
        redis=redis,
    )
    return result
