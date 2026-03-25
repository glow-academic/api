"""Tests for delete_cohorts — black-box using tool functions only."""

import pytest
from tests.helpers import nonexistent_id, unique_tag

from app.tools.artifacts.cohort.create import create_cohort
from app.tools.artifacts.cohort.delete import delete_cohorts
from app.tools.artifacts.cohort.get import get_cohorts
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


async def test_hard_delete_single(conn, redis_client):
    """Hard delete removes the artifact."""
    name = await create_name(conn, f"del-{_u()}", redis_client)
    p = await create_cohort(conn, name_id=name.id)

    result = await delete_cohorts(conn, [p.id])
    assert p.id in result.deleted_ids

    got = await get_cohorts(conn, [p.id], active=None)
    assert len(got) == 0


async def test_hard_delete_multiple(conn, redis_client):
    """Hard delete works on multiple IDs."""
    ids = []
    for _ in range(3):
        name = await create_name(conn, f"del-{_u()}", redis_client)
        p = await create_cohort(conn, name_id=name.id)
        ids.append(p.id)

    result = await delete_cohorts(conn, ids)
    assert set(result.deleted_ids) == set(ids)

    got = await get_cohorts(conn, ids)
    assert len(got) == 0


async def test_hard_delete_nonexistent(conn, redis_client):
    """Deleting a nonexistent ID returns empty deleted_ids."""
    fake_id = nonexistent_id()
    result = await delete_cohorts(conn, [fake_id])
    assert result.deleted_ids == []


async def test_hard_delete_empty_list(conn, redis_client):
    """Empty input returns empty result."""
    result = await delete_cohorts(conn, [])
    assert result.deleted_ids == []


async def test_soft_delete_sets_inactive(conn, redis_client):
    """Soft delete sets active=false, artifact still exists."""
    name = await create_name(conn, f"soft-{_u()}", redis_client)
    p = await create_cohort(conn, name_id=name.id)

    result = await delete_cohorts(conn, [p.id], soft=True)
    assert p.id in result.deleted_ids

    # Still exists but inactive
    got = await get_cohorts(conn, [p.id], active=None)
    assert len(got) == 1
    assert got[0].active is False  # get filters active=true by default


async def test_soft_delete_recoverable(conn, redis_client):
    """Soft-deleted artifact is still in the database."""
    name = await create_name(conn, f"recover-{_u()}", redis_client)
    p = await create_cohort(conn, name_id=name.id)

    await delete_cohorts(conn, [p.id], soft=True)

    # Verify it's still in DB, just inactive
    row = await conn.fetchrow(
        "SELECT id, active FROM cohort_artifact WHERE id = $1", p.id
    )
    assert row is not None
    assert row["active"] is False


async def test_hard_delete_cascades_junctions(conn, redis_client):
    """Hard delete cascades to junction rows."""
    name = await create_name(conn, f"cascade-{_u()}", redis_client)
    p = await create_cohort(conn, name_id=name.id)

    await delete_cohorts(conn, [p.id])

    # Junction row should be gone
    row = await conn.fetchrow(
        "SELECT 1 FROM cohort_names_junction WHERE cohort_id = $1", p.id
    )
    assert row is None
