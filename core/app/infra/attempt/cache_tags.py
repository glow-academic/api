"""Shared per-profile read-cache tag construction for attempt mutations.

The home + practice page read-caches register their entries under a
per-profile tag *on top of* their shared ``["home"/"practice", "get"]`` tags:

    core/app/routes/attempt/home.py     : tags + [f"home:profile:{pid}"]
    core/app/routes/attempt/practice.py : tags + [f"practice:profile:{pid}"]

Crucially they carry NO ``artifacts``/``attempt`` tag — so the
complete/grade/refresh invalidation (``refresh_attempt_impl`` busts
``["attempt", "artifacts"]``) and the WS run-complete bust (``["attempts"]``)
land on a DISJOINT tag set and never reach the home/practice caches. After a
student finishes a sim (new best score / first pass) the home/practice cards
keep serving the stale ``highest_score_percent`` / "passed" badge for up to
their 300s TTL.

Busting these per-profile tags from the mutate side closes that gap. The
``POST /attempt/archive`` route already does this (see
``build_attempt_archive_invalidation_tags``); this helper centralizes the
per-profile tag construction so the archive route and the
complete/grade/refresh path share one source of truth.
"""

from __future__ import annotations

from uuid import UUID


def build_attempt_profile_cache_tags(profile_id: UUID | str) -> list[str]:
    """Per-profile read-cache tags an attempt mutation must bust.

    Mirrors the per-profile tags the home/practice reads register under
    (``home:profile:{pid}`` / ``practice:profile:{pid}``) — the only
    attempt-derived caches that omit the shared ``artifacts`` umbrella tag.
    """
    pid = str(profile_id)
    return [f"home:profile:{pid}", f"practice:profile:{pid}"]
