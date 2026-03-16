"""Tests for create_scenario — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.scenario.create import create_scenario
from app.tools.artifacts.scenario.get import get_scenarios
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.flags.create import create_flag
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


async def test_creates_bare_artifact(conn, redis_client):
    result = await create_scenario(conn)
    assert result.id is not None
    items = await get_scenarios(conn, [result.id])
    assert len(items) == 1
    assert items[0].generated is False
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, redis_client):
    result = await create_scenario(conn, mcp=True)
    items = await get_scenarios(conn, [result.id])
    assert items[0].mcp is True


async def test_links_single_select_junctions(conn, redis_client):
    name = await create_name(conn, f"n-{_u()}", redis_client)
    desc = await create_description(conn, f"d-{_u()}", redis_client)
    result = await create_scenario(conn, name_id=name.id, description_id=desc.id)
    items = await get_scenarios(conn, [result.id], names=True, descriptions=True)
    p = items[0]
    assert p.name_ids == [name.id]
    assert p.description_ids == [desc.id]


async def test_links_multi_select_junctions(conn, redis_client):
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)
    result = await create_scenario(conn, department_ids=[d1.id, d2.id])
    items = await get_scenarios(conn, [result.id], departments=True)
    assert set(items[0].department_ids) == {d1.id, d2.id}


async def test_links_flags_with_value(conn, redis_client):
    f1 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    f2 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    result = await create_scenario(conn, flag_ids=[f1.id, f2.id])
    items = await get_scenarios(conn, [result.id], flags=True)
    assert set(items[0].flag_ids) == {f1.id, f2.id}


async def test_no_junctions_when_none_provided(conn, redis_client):
    result = await create_scenario(conn)
    items = await get_scenarios(
        conn,
        [result.id],
        names=True,
        descriptions=True,
        departments=True,
        flags=True,
        documents=True,
        images=True,
        objectives=True,
        options=True,
        parameter_fields=True,
        personas=True,
        problem_statements=True,
        questions=True,
        videos=True,
        scenarios=True,
    )
    p = items[0]
    assert p.name_ids == []
    assert p.department_ids == []
    assert p.flag_ids == []
    assert p.document_ids == []
    assert p.image_ids == []
    assert p.objective_ids == []
    assert p.option_ids == []
    assert p.parameter_field_ids == []
    assert p.persona_ids == []
    assert p.problem_statement_ids == []
    assert p.question_ids == []
    assert p.video_ids == []
    assert p.scenario_ids == []
