"""Tests for rubric point denormalization."""

import pytest

from app.infra.rubric.permissions_context import resolve_rubric_point_totals
from app.tools.resources.points.create import create_point
from app.tools.resources.standard_groups.create import create_standard_group
from app.tools.resources.standards.create import create_standard
from tests.helpers import unique_tag

pytestmark = pytest.mark.asyncio


async def test_rubric_max_points_use_standard_groups_not_levels(pool, redis_client):
    tag = unique_tag()
    async with pool.acquire() as conn:
        pass_point = await create_point(conn, 8, redis_client, point_type="pass")
        groups = [
            await create_standard_group(
                conn,
                f"Criterion {tag} A",
                f"CA {tag}",
                "Criterion A",
                5,
                4,
                redis_client,
            ),
            await create_standard_group(
                conn,
                f"Criterion {tag} B",
                f"CB {tag}",
                "Criterion B",
                5,
                4,
                redis_client,
            ),
        ]
        standards = []
        for group in groups:
            for points in (5, 4, 3):
                standards.append(
                    await create_standard(
                        conn,
                        f"{group.short_name} level {points}",
                        "level",
                        points,
                        group.id,
                        redis_client,
                    )
                )

    pass_points, total_points = await resolve_rubric_point_totals(
        pool,
        redis_client,
        pass_points_id=pass_point.id,
        standard_group_ids=[group.id for group in groups],
        standard_ids=[standard.id for standard in standards],
    )

    assert pass_points == 8
    assert total_points == 10
