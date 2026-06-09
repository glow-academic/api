"""Tests for search_profiles — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.profile.create import create_profile
from app.tools.artifacts.profile.search import search_profiles
from app.tools.resources.departments.create import create_department
from app.tools.resources.names.create import create_name
from app.tools.resources.roles.create import create_role

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_bare_search_returns_results(conn, redis_client):
    """A profile with a name should be findable via search.

    Scope the search to this test's own profile via the unique name tag.
    ``search_profiles`` defaults to ``limit_count=20`` ordered by name, so in
    the shared process (where sibling ``pool``-fixture tests commit hundreds of
    profiles that escape the per-test transaction rollback) an unfiltered
    ``search_profiles(conn)`` returns only the first 20-by-name and pages this
    fresh profile out of the result window. Searching by the unique name tag
    bounds the result to exactly this profile, asserting presence robustly and
    independent of how many sibling profiles exist — mirroring the id-scoped
    approach in ``test_exclude_ids``.
    """
    tag = _u()
    name = await create_name(conn, f"bare-{tag}", redis_client)
    p = await create_profile(conn, name_id=name.id)

    ids, _total = await search_profiles(conn, search=f"bare-{tag}")
    assert p.id in ids


async def test_text_search_filters_by_name(conn, redis_client):
    """Text search matches name substring."""
    tag = _u()
    name_match = await create_name(conn, f"match-{tag}", redis_client)
    name_other = await create_name(conn, f"other-{_u()}", redis_client)

    p1 = await create_profile(conn, name_id=name_match.id)
    p2 = await create_profile(conn, name_id=name_other.id)

    ids, _total = await search_profiles(conn, search=f"match-{tag}")
    assert p1.id in ids
    assert p2.id not in ids


async def test_department_filter(conn, redis_client):
    """Filter by department_ids returns only matching profiles."""
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)

    p1 = await create_profile(conn, department_ids=[d1.id])
    p2 = await create_profile(conn, department_ids=[d2.id])

    ids, _total = await search_profiles(conn, department_ids=[d1.id])
    assert p1.id in ids
    assert p2.id not in ids


async def test_exclude_ids(conn, redis_client):
    """Excluded profiles should not appear in results."""
    tag = _u()
    name = await create_name(conn, f"excl-{tag}", redis_client)
    p1 = await create_profile(conn, name_id=name.id)
    p2 = await create_profile(conn, name_id=name.id)

    # Scope the search to this test's own profiles via the unique name tag.
    # ``search_profiles`` defaults to ``limit_count=20`` ordered by name, so
    # in the shared template DB (which holds many sibling profiles) an
    # unfiltered search can page ``p2`` out of the result set and break the
    # ``p2.id in ids`` assertion. Filtering by the unique name bounds the
    # result to exactly p1/p2, making the exclude assertions id-scoped and
    # robust to contamination.
    ids, _total = await search_profiles(
        conn, search=f"excl-{tag}", exclude_ids=[p1.id]
    )
    assert p1.id not in ids
    assert p2.id in ids


async def test_pagination(conn, redis_client):
    """Pagination with limit and offset works."""
    tag = _u()
    created = []
    for i in range(5):
        name = await create_name(conn, f"page-{tag}-{i:02d}", redis_client)
        p = await create_profile(conn, name_id=name.id)
        created.append(p.id)

    page1, _total = await search_profiles(
        conn, search=f"page-{tag}", limit_count=2, offset_count=0
    )
    page2, _total = await search_profiles(
        conn, search=f"page-{tag}", limit_count=2, offset_count=2
    )
    page3, _total = await search_profiles(
        conn, search=f"page-{tag}", limit_count=2, offset_count=4
    )

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    # No overlap
    all_ids = page1 + page2 + page3
    assert len(set(all_ids)) == 5


async def test_active_only_default(conn, redis_client):
    """Inactive profiles excluded by default."""
    p = await create_profile(conn, active=False)

    ids, _total = await search_profiles(conn)
    assert p.id not in ids


async def test_active_only_false_includes_inactive(conn, redis_client):
    """active_only=False includes inactive profiles."""
    name = await create_name(conn, f"inactive-{_u()}", redis_client)
    p = await create_profile(conn, active=False, name_id=name.id)

    ids, _total = await search_profiles(conn, search=name.name, active_only=False)
    assert p.id in ids


async def test_exclude_role_ids_keeps_roleless_profiles(conn, redis_client):
    """Role-hierarchy scoping via exclude_role_ids must keep roleless profiles.

    Regression for the profiles-bulk / profiles-edit demos: a name-only
    profile (no role junction) was created successfully but never appeared in
    /profile/search, because the search scoped visibility with an *inclusion*
    role filter (profile must carry an allowed role). A roleless profile
    carries no privilege and must remain visible — expressed as the negative
    ``exclude_role_ids`` filter (exclude only roles above the actor's level).
    """
    tag = _u()
    name_roleless = await create_name(conn, f"roleless-{tag}", redis_client)
    name_roled = await create_name(conn, f"roled-{tag}", redis_client)
    higher_role = await create_role(
        conn, redis_client, name=f"role-{tag}", level=0
    )

    p_roleless = await create_profile(conn, name_id=name_roleless.id)
    p_roled = await create_profile(
        conn, name_id=name_roled.id, role_ids=[higher_role.id]
    )

    # Negative scoping: exclude the higher-privilege role. The roleless
    # profile stays; the profile carrying that role is filtered out.
    ids, _total = await search_profiles(
        conn, search=tag, exclude_role_ids=[higher_role.id]
    )
    assert p_roleless.id in ids
    assert p_roled.id not in ids

    # The old inclusion semantics would have dropped the roleless profile —
    # this documents exactly why the demos broke.
    inc_ids, _ = await search_profiles(
        conn, search=tag, role_ids=[higher_role.id]
    )
    assert p_roleless.id not in inc_ids
    assert p_roled.id in inc_ids
