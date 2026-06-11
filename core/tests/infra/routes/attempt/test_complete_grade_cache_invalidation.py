"""Cache-invalidation completeness test for the attempt complete/grade/refresh
path (and the simulation-rename path) vs the home/practice read-caches.

Class: cache-invalidation INCOMPLETENESS → stale reads. The home + practice
page read-caches register their entries under a per-profile tag *on top of*
their shared ``["home"/"practice", "get"]`` tags and carry NO
``artifacts``/``attempt`` tag:

  core/app/routes/attempt/home.py     : ["home", "get", f"home:profile:{pid}"]
  core/app/routes/attempt/practice.py : ["practice", "get", f"practice:profile:{pid}"]

Pre-fix the complete/grade/refresh path (``refresh_attempt_impl``) busted only
``["attempt", "artifacts"]`` and the WS run-complete path only ``["attempts"]``
— a DISJOINT tag set — so after a student finished a sim (new best score /
first pass) the home/practice cards served the stale
``highest_score_percent`` / "passed" badge for up to the 300s TTL. The sibling
``POST /attempt/archive`` route already busted the per-profile
``home/practice:profile:*`` tags; the complete/grade path never got that
treatment.

Post-fix ``refresh_attempt_impl`` appends ``build_attempt_profile_cache_tags``
(the shared per-profile constructor the archive route now reuses), and a sim
mutation busts the GLOBAL ``home``/``practice`` tags. These tests exercise the
real cache layer (``set_cached`` / ``invalidate_tags`` against the Redis
testcontainer, redis passed as an explicit param) so they're a faithful repro
independent of any MV / DB timing.
"""

from __future__ import annotations

import pytest

from app.infra.attempt.cache_tags import build_attempt_profile_cache_tags
from app.infra.attempt.refresh import _TAGS as ATTEMPT_REFRESH_TAGS
from app.infra.simulation.refresh import _TAGS as SIMULATION_REFRESH_TAGS
from app.utils.cache.get_cached import get_cached
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.cache.set_cached import set_cached

_PROFILE_ID = "11111111-1111-1111-1111-111111111111"

# Tags copied from the cached READ side (the values these reads pass to
# ``set_cached``) — kept literal so the test pins the actual read contract:
#   core/app/routes/attempt/home.py     : tags + [f"home:profile:{pid}"]
#   core/app/routes/attempt/practice.py : tags + [f"practice:profile:{pid}"]
_HOME_READ_TAGS = ["home", "get", f"home:profile:{_PROFILE_ID}"]
_PRACTICE_READ_TAGS = ["practice", "get", f"practice:profile:{_PROFILE_ID}"]


async def _seed(key: str, tags: list[str], *, redis) -> None:
    await set_cached(key, {"data": {"sentinel": key}}, ttl=300, tags=tags, redis=redis)


def test_profile_cache_tags_match_home_practice_read_contract():
    """The shared helper must emit exactly the per-profile tags the
    home/practice reads register under."""
    tags = build_attempt_profile_cache_tags(_PROFILE_ID)
    assert tags == [
        f"home:profile:{_PROFILE_ID}",
        f"practice:profile:{_PROFILE_ID}",
    ]


def test_pre_fix_attempt_tags_were_disjoint_from_home_practice():
    """Documents the original gap: ``["attempt","artifacts"]`` shares no tag
    with the home/practice read tag sets — so they could never be busted by
    the static-tag-only invalidation."""
    static = {"attempt", "artifacts", "attempts"}
    assert static.isdisjoint(set(_HOME_READ_TAGS))
    assert static.isdisjoint(set(_PRACTICE_READ_TAGS))


@pytest.mark.asyncio
async def test_attempt_complete_grade_busts_home_practice_caches(redis_client):
    """A complete/grade/refresh (``refresh_attempt_impl``) must bust the
    per-profile home/practice caches.

    Seeds a home-response and practice-response cache entry under the exact
    tags their reads use, then invalidates the tag set the refresh path now
    emits (``_TAGS + build_attempt_profile_cache_tags(profile_id)``). Both
    must be gone. Pre-fix (static ``_TAGS`` alone) they survived.
    """
    redis = redis_client
    home_key = "http:/home:abc"
    practice_key = "http:/practice:def"

    await _seed(home_key, _HOME_READ_TAGS, redis=redis)
    await _seed(practice_key, _PRACTICE_READ_TAGS, redis=redis)
    assert await get_cached(home_key, redis=redis) is not None
    assert await get_cached(practice_key, redis=redis) is not None

    # Pre-fix behaviour: static tags alone leave both caches stale.
    await invalidate_tags(list(ATTEMPT_REFRESH_TAGS), redis=redis)
    assert await get_cached(home_key, redis=redis) is not None, (
        "static ['attempt','artifacts'] should NOT reach the home cache"
    )
    assert await get_cached(practice_key, redis=redis) is not None

    # Post-fix: the actual tag set the refresh path emits.
    refresh_tags = list(ATTEMPT_REFRESH_TAGS) + build_attempt_profile_cache_tags(
        _PROFILE_ID
    )
    await invalidate_tags(refresh_tags, redis=redis)

    assert await get_cached(home_key, redis=redis) is None, (
        "stale read: home cache survived attempt complete/grade invalidation"
    )
    assert await get_cached(practice_key, redis=redis) is None, (
        "stale read: practice cache survived attempt complete/grade invalidation"
    )


@pytest.mark.asyncio
async def test_simulation_rename_busts_all_home_practice_caches(redis_client):
    """A simulation mutation (e.g. rename) must bust the home/practice caches
    of EVERY student who sees that sim, via the global ``home``/``practice``
    tags now carried by ``refresh_simulation_impl``."""
    redis = redis_client
    # Two distinct students' home/practice entries.
    other_pid = "22222222-2222-2222-2222-222222222222"
    keys = {
        "http:/home:p1": ["home", "get", f"home:profile:{_PROFILE_ID}"],
        "http:/home:p2": ["home", "get", f"home:profile:{other_pid}"],
        "http:/practice:p1": ["practice", "get", f"practice:profile:{_PROFILE_ID}"],
        "http:/practice:p2": ["practice", "get", f"practice:profile:{other_pid}"],
    }
    for key, tags in keys.items():
        await _seed(key, tags, redis=redis)
        assert await get_cached(key, redis=redis) is not None

    await invalidate_tags(list(SIMULATION_REFRESH_TAGS), redis=redis)

    for key in keys:
        assert await get_cached(key, redis=redis) is None, (
            f"stale read: {key} survived simulation-rename invalidation"
        )
