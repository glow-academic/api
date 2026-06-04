"""Tests for delete_settings — black-box using tool functions only."""

import pytest
from tests.helpers import nonexistent_id, unique_tag

from app.tools.artifacts.setting.create import create_setting
from app.tools.artifacts.setting.delete import delete_settings
from app.tools.artifacts.setting.get import get_settings
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


async def test_hard_delete_single(conn, redis_client):
    """Hard delete removes the artifact."""
    name = await create_name(conn, f"del-{_u()}", redis_client)
    p = await create_setting(conn, name_id=name.id)

    result = await delete_settings(conn, [p.id])
    assert p.id in result.deleted_ids

    got = await get_settings(conn, [p.id], active=None)
    assert len(got) == 0


async def test_hard_delete_multiple(conn, redis_client):
    """Hard delete works on multiple IDs."""
    ids = []
    for _ in range(3):
        name = await create_name(conn, f"del-{_u()}", redis_client)
        p = await create_setting(conn, name_id=name.id)
        ids.append(p.id)

    result = await delete_settings(conn, ids)
    assert set(result.deleted_ids) == set(ids)

    got = await get_settings(conn, ids)
    assert len(got) == 0


async def test_hard_delete_nonexistent(conn, redis_client):
    """Deleting a nonexistent ID returns empty deleted_ids."""
    fake_id = nonexistent_id()
    result = await delete_settings(conn, [fake_id])
    assert result.deleted_ids == []


async def test_hard_delete_empty_list(conn, redis_client):
    """Empty input returns empty result."""
    result = await delete_settings(conn, [])
    assert result.deleted_ids == []


async def test_soft_delete_sets_inactive(conn, redis_client):
    """Soft delete sets active=false, artifact still exists."""
    name = await create_name(conn, f"soft-{_u()}", redis_client)
    p = await create_setting(conn, name_id=name.id)

    result = await delete_settings(conn, [p.id], soft=True)
    assert p.id in result.deleted_ids

    # Still exists but inactive
    got = await get_settings(conn, [p.id], active=None)
    assert len(got) == 1
    assert got[0].active is False  # get filters active=true by default


async def test_soft_delete_recoverable(conn, redis_client):
    """Soft-deleted artifact is still in the database."""
    name = await create_name(conn, f"recover-{_u()}", redis_client)
    p = await create_setting(conn, name_id=name.id)

    await delete_settings(conn, [p.id], soft=True)

    # Verify it's still in DB, just inactive
    row = await conn.fetchrow(
        "SELECT id, active FROM setting_artifact WHERE id = $1", p.id
    )
    assert row is not None
    assert row["active"] is False


async def test_hard_delete_cascades_junctions(conn, redis_client):
    """Hard delete cascades to junction rows."""
    name = await create_name(conn, f"cascade-{_u()}", redis_client)
    p = await create_setting(conn, name_id=name.id)

    await delete_settings(conn, [p.id])

    # Junction row should be gone
    row = await conn.fetchrow(
        "SELECT 1 FROM setting_names_junction WHERE setting_id = $1", p.id
    )
    assert row is None


async def test_hard_delete_clears_non_cascading_systems_junction(
    conn, redis_client
):
    """Hard-deleting a setting that has a ``systems`` link must succeed.

    The ``setting_systems_junction.setting_id`` FK was created WITHOUT
    ``ON DELETE CASCADE`` (NO ACTION). Before the fix, a plain
    ``DELETE FROM setting_artifact`` raised ForeignKeyViolationError for any
    setting with a systems/mcp/logins link, making the artifact undeletable.
    The delete tool now clears the non-cascading junctions first.

    Fail-pre: this raised ForeignKeyViolationError.
    Pass-post: delete succeeds and the junction row is gone.
    """
    from app.tools.resources.systems.create import create_system

    system = await create_system(conn, name=f"s-{_u()}", redis=redis_client)
    p = await create_setting(conn, system_ids=[system.id])

    pre = await conn.fetchval(
        "SELECT count(*) FROM setting_systems_junction WHERE setting_id = $1", p.id
    )
    assert pre == 1

    result = await delete_settings(conn, [p.id])
    assert p.id in result.deleted_ids

    assert await conn.fetchval(
        "SELECT count(*) FROM setting_artifact WHERE id = $1", p.id
    ) == 0
    assert await conn.fetchval(
        "SELECT count(*) FROM setting_systems_junction WHERE setting_id = $1", p.id
    ) == 0
