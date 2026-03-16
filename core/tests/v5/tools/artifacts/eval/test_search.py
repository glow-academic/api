"""Tests for search_evals — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.eval.create import create_eval
from app.tools.artifacts.eval.search import search_evals
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_bare_search_returns_results(conn, redis_client):
    """An eval with a name should appear in an unfiltered search."""
    name = await create_name(conn, f"bare-{_u()}", redis_client)
    e = await create_eval(conn, name_id=name.id)

    ids, _total = await search_evals(conn)
    assert e.id in ids


async def test_text_search_filters_by_name(conn, redis_client):
    """Text search matches name substring."""
    tag = _u()
    name_match = await create_name(conn, f"match-{tag}", redis_client)
    name_other = await create_name(conn, f"other-{_u()}", redis_client)

    e1 = await create_eval(conn, name_id=name_match.id)
    e2 = await create_eval(conn, name_id=name_other.id)

    ids, _total = await search_evals(conn, search=f"match-{tag}")
    assert e1.id in ids
    assert e2.id not in ids


async def test_text_search_filters_by_description(conn, redis_client):
    """Text search also matches description text."""
    tag = _u()
    desc = await create_description(conn, f"desc-{tag}", redis_client)

    e1 = await create_eval(conn, description_id=desc.id)
    e2 = await create_eval(conn)

    ids, _total = await search_evals(conn, search=f"desc-{tag}")
    assert e1.id in ids
    assert e2.id not in ids


async def test_department_filter(conn, redis_client):
    """Filter by department_ids returns only matching evals."""
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)

    e1 = await create_eval(conn, department_ids=[d1.id])
    e2 = await create_eval(conn, department_ids=[d2.id])

    ids, _total = await search_evals(conn, department_ids=[d1.id])
    assert e1.id in ids
    assert e2.id not in ids


async def test_exclude_ids(conn, redis_client):
    """Excluded evals should not appear in results."""
    name = await create_name(conn, f"excl-{_u()}", redis_client)
    e1 = await create_eval(conn, name_id=name.id)
    e2 = await create_eval(conn, name_id=name.id)

    ids, _total = await search_evals(conn, exclude_ids=[e1.id])
    assert e1.id not in ids
    assert e2.id in ids


async def test_pagination(conn, redis_client):
    """Pagination with limit and offset works."""
    tag = _u()
    created = []
    for i in range(5):
        name = await create_name(conn, f"page-{tag}-{i:02d}", redis_client)
        e = await create_eval(conn, name_id=name.id)
        created.append(e.id)

    page1, _total = await search_evals(
        conn, search=f"page-{tag}", limit_count=2, offset_count=0
    )
    page2, _total = await search_evals(
        conn, search=f"page-{tag}", limit_count=2, offset_count=2
    )
    page3, _total = await search_evals(
        conn, search=f"page-{tag}", limit_count=2, offset_count=4
    )

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    # No overlap
    all_ids = page1 + page2 + page3
    assert len(set(all_ids)) == 5


async def test_active_only_default(conn, redis_client):
    """Inactive evals excluded by default."""
    e = await create_eval(conn, active=False)

    ids, _total = await search_evals(conn)
    assert e.id not in ids


async def test_active_only_false_includes_inactive(conn, redis_client):
    """active_only=False includes inactive evals."""
    name = await create_name(conn, f"inactive-{_u()}", redis_client)
    e = await create_eval(conn, active=False, name_id=name.id)

    ids, _total = await search_evals(conn, search=name.name, active_only=False)
    assert e.id in ids
