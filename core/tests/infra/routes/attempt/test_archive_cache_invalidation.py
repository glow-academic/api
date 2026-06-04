"""Cache-invalidation completeness test for ``POST /attempt/archive``.

Class: cache-invalidation INCOMPLETENESS → stale reads. Archiving an attempt
flips its ``is_archived`` flag, removing it from every default
(non-archived) attempt-derived view. Several of those views cache their
response under the shared ``artifacts`` umbrella tag but NOT under the
``dashboard`` / per-profile ``home/practice/...`` tags that the archive route
busted pre-fix:

  - leaderboard bundle   → tags ``["artifacts", "leaderboard"]``
  - record/profile report → tags ``["artifacts", "record", "views", "analytics"]``

Pre-fix the route busted ``["attempts", "dashboard", home/reports/practice/
history:profile:*]`` — none of which intersect those tag sets — so the
leaderboard and record caches kept serving the now-archived attempt for up
to their 300s TTL. The sibling ``POST /test/archive`` route busts
``["benchmark", "test", "artifacts"]`` (the ``artifacts`` umbrella), and the
attempt run-complete / grade paths bust ``["attempt", "artifacts"]`` — the
archive path simply omitted ``artifacts``.

The test exercises the real cache layer (``set_cached`` / ``invalidate_tags``
against the Redis testcontainer, redis passed as an explicit param) and the
route's own tag-builder, so it is a faithful repro independent of any MV /
DB timing. Fails pre-fix (leaderboard + record caches survive the archive
invalidation), passes post-fix (both are busted).
"""

from __future__ import annotations

import pytest

from app.routes.attempt.archive import build_attempt_archive_invalidation_tags
from app.utils.cache.get_cached import get_cached
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.cache.set_cached import set_cached

# Tag sets copied from the cached READ side (the values these reads pass to
# ``set_cached``) — kept literal so the test pins the actual read contract:
#   core/app/infra/leaderboard/get.py : tags = ["artifacts", "leaderboard"]
#   core/app/infra/record/get.py      : tags = ["artifacts", "record", "views", "analytics"]
_LEADERBOARD_READ_TAGS = ["artifacts", "leaderboard"]
_RECORD_READ_TAGS = ["artifacts", "record", "views", "analytics"]


async def _seed(key: str, tags: list[str], *, redis) -> None:
    await set_cached(key, {"data": {"sentinel": key}}, ttl=300, tags=tags, redis=redis)


@pytest.mark.asyncio
async def test_attempt_archive_invalidates_attempt_derived_caches(redis_client):
    """Archiving an attempt must bust the attempt-derived view caches.

    Seeds a leaderboard-response cache entry and a record-report cache entry
    (under the exact tags their reads use), then runs the archive route's
    invalidation against the real cache layer. Both entries must be gone —
    pre-fix they survived because the route omitted the ``artifacts`` tag.
    """
    redis = redis_client
    profile_id = "11111111-1111-1111-1111-111111111111"

    leaderboard_key = "http:/leaderboard/get:abc"
    record_key = "http:/record/get:def"

    await _seed(leaderboard_key, _LEADERBOARD_READ_TAGS, redis=redis)
    await _seed(record_key, _RECORD_READ_TAGS, redis=redis)

    # Sanity: both reads are warm before the mutate.
    assert await get_cached(leaderboard_key, redis=redis) is not None
    assert await get_cached(record_key, redis=redis) is not None

    # The mutate: invalidate exactly the tags the archive route builds.
    tags = build_attempt_archive_invalidation_tags([profile_id])
    await invalidate_tags(tags, redis=redis)

    # Post-mutate: a subsequent read must MISS (fresh recompute), not serve
    # the stale pre-archive bundle. Pre-fix these assertions fail because the
    # cached entries (tagged ``artifacts``) are untouched by the route's
    # ``["attempts", "dashboard", ...]`` tag set.
    assert await get_cached(leaderboard_key, redis=redis) is None, (
        "stale read: leaderboard cache (tags ['artifacts','leaderboard']) "
        "survived attempt-archive invalidation — the now-archived attempt is "
        "served until the 300s TTL"
    )
    assert await get_cached(record_key, redis=redis) is None, (
        "stale read: record-report cache (tags ['artifacts','record',...]) "
        "survived attempt-archive invalidation"
    )


@pytest.mark.asyncio
async def test_attempt_archive_tags_include_artifacts_umbrella():
    """The builder must emit the ``artifacts`` umbrella + preserve prior tags."""
    tags = build_attempt_archive_invalidation_tags(["p1", "p2"])
    assert "artifacts" in tags
    # Intent preserved: the original tags are still busted.
    assert "attempts" in tags
    assert "dashboard" in tags
    for pid in ("p1", "p2"):
        assert f"home:profile:{pid}" in tags
        assert f"reports:profile:{pid}" in tags
        assert f"practice:profile:{pid}" in tags
        assert f"history:profile:{pid}" in tags

    # Empty profile list still busts the global umbrella tags.
    base = build_attempt_archive_invalidation_tags(None)
    assert base == ["attempts", "dashboard", "artifacts"]
