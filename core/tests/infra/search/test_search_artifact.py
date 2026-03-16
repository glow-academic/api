"""Tests for infra.search.search_artifact — shared SQL-builder helpers.

Uses persona_* tables as a concrete test bed, but the helpers
themselves are artifact-agnostic.
"""

import pytest
from tests.helpers import unique_tag

from app.infra.search.search_artifact import (
    add_junction_filter,
    add_text_search,
    execute_artifact_search,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _u() -> str:
    return unique_tag()


async def _make_persona(conn, *, active=True):
    return await conn.fetchval(
        "INSERT INTO persona_artifact (active, generated, mcp) "
        "VALUES ($1, false, false) RETURNING id",
        active,
    )


async def _make_name(conn, name: str):
    return await conn.fetchval(
        "INSERT INTO names_resource (name) VALUES ($1) RETURNING id", name
    )


async def _make_description(conn, desc: str):
    return await conn.fetchval(
        "INSERT INTO descriptions_resource (description) VALUES ($1) RETURNING id",
        desc,
    )


async def _make_dept(conn):
    return await conn.fetchval(
        "INSERT INTO departments_resource DEFAULT VALUES RETURNING id"
    )


async def _make_flag(conn):
    return await conn.fetchval(
        "INSERT INTO flags_resource (name, description, icon) "
        "VALUES ($1, 'desc', 'icon') RETURNING id",
        f"flag-{_u()}",
    )


async def _link_name(conn, persona_id, name_id):
    await conn.execute(
        "INSERT INTO persona_names_junction (persona_id, names_id) VALUES ($1, $2)",
        persona_id,
        name_id,
    )


async def _link_description(conn, persona_id, desc_id):
    await conn.execute(
        "INSERT INTO persona_descriptions_junction (persona_id, descriptions_id) "
        "VALUES ($1, $2)",
        persona_id,
        desc_id,
    )


async def _link_dept(conn, persona_id, dept_id):
    await conn.execute(
        "INSERT INTO persona_departments_junction (persona_id, departments_id) "
        "VALUES ($1, $2)",
        persona_id,
        dept_id,
    )


async def _link_flag(conn, persona_id, flag_id):
    await conn.execute(
        "INSERT INTO persona_flags_junction (persona_id, flags_id) VALUES ($1, $2)",
        persona_id,
        flag_id,
    )


# ---------------------------------------------------------------------------
# add_junction_filter
# ---------------------------------------------------------------------------


async def test_junction_filter_matches(conn):
    """add_junction_filter builds an EXISTS condition that matches."""
    pid = await _make_persona(conn)
    did = await _make_dept(conn)
    await _link_dept(conn, pid, did)

    conditions: list[str] = []
    params: list[object] = []
    idx = add_junction_filter(
        conditions,
        params,
        1,
        junction_table="persona_departments_junction",
        owner_col="persona_id",
        resource_col="departments_id",
        ids=[did],
    )

    assert idx == 2
    assert len(conditions) == 1
    assert len(params) == 1

    ids, _total = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=conditions,
        params=params,
        idx=idx,
    )
    assert pid in ids


async def test_junction_filter_excludes_non_matching(conn):
    """Personas without the junction link are excluded."""
    pid = await _make_persona(conn)
    did = await _make_dept(conn)
    # Deliberately NOT linking

    conditions: list[str] = []
    params: list[object] = []
    idx = add_junction_filter(
        conditions,
        params,
        1,
        junction_table="persona_departments_junction",
        owner_col="persona_id",
        resource_col="departments_id",
        ids=[did],
    )

    ids, _total = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=conditions,
        params=params,
        idx=idx,
    )
    assert pid not in ids


async def test_junction_filter_ignores_inactive_links(conn):
    """Inactive junction rows should not match."""
    pid = await _make_persona(conn)
    did = await _make_dept(conn)
    await _link_dept(conn, pid, did)
    # Deactivate the link
    await conn.execute(
        "UPDATE persona_departments_junction SET active = false "
        "WHERE persona_id = $1 AND departments_id = $2",
        pid,
        did,
    )

    conditions: list[str] = []
    params: list[object] = []
    idx = add_junction_filter(
        conditions,
        params,
        1,
        junction_table="persona_departments_junction",
        owner_col="persona_id",
        resource_col="departments_id",
        ids=[did],
    )

    ids, _total = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=conditions,
        params=params,
        idx=idx,
    )
    assert pid not in ids


# ---------------------------------------------------------------------------
# add_text_search
# ---------------------------------------------------------------------------


async def test_text_search_matches_substring(conn):
    """add_text_search matches a name substring via junction → resource."""
    tag = _u()
    pid = await _make_persona(conn)
    nid = await _make_name(conn, f"hello-{tag}-world")
    await _link_name(conn, pid, nid)

    conditions: list[str] = []
    params: list[object] = []
    idx = add_text_search(
        conditions,
        params,
        1,
        junction_table="persona_names_junction",
        owner_col="persona_id",
        resource_col="names_id",
        resource_table="names_resource",
        text_col="name",
        search=tag,
    )

    assert idx == 2

    ids, _total = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=conditions,
        params=params,
        idx=idx,
    )
    assert pid in ids


async def test_text_search_case_insensitive(conn):
    """Text search is case-insensitive."""
    tag = _u()
    pid = await _make_persona(conn)
    nid = await _make_name(conn, f"UPPER-{tag}")
    await _link_name(conn, pid, nid)

    conditions: list[str] = []
    params: list[object] = []
    idx = add_text_search(
        conditions,
        params,
        1,
        junction_table="persona_names_junction",
        owner_col="persona_id",
        resource_col="names_id",
        resource_table="names_resource",
        text_col="name",
        search=f"upper-{tag}",
    )

    ids, _total = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=conditions,
        params=params,
        idx=idx,
    )
    assert pid in ids


async def test_text_search_no_match(conn):
    """Text search excludes non-matching names."""
    pid = await _make_persona(conn)
    nid = await _make_name(conn, f"alpha-{_u()}")
    await _link_name(conn, pid, nid)

    conditions: list[str] = []
    params: list[object] = []
    idx = add_text_search(
        conditions,
        params,
        1,
        junction_table="persona_names_junction",
        owner_col="persona_id",
        resource_col="names_id",
        resource_table="names_resource",
        text_col="name",
        search="zzz-nomatch-zzz",
    )

    ids, _total = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=conditions,
        params=params,
        idx=idx,
    )
    assert pid not in ids


async def test_text_search_on_description(conn):
    """Text search works through description junction too."""
    tag = _u()
    pid = await _make_persona(conn)
    did = await _make_description(conn, f"some-desc-{tag}")
    await _link_description(conn, pid, did)

    conditions: list[str] = []
    params: list[object] = []
    idx = add_text_search(
        conditions,
        params,
        1,
        junction_table="persona_descriptions_junction",
        owner_col="persona_id",
        resource_col="descriptions_id",
        resource_table="descriptions_resource",
        text_col="description",
        search=tag,
    )

    ids, _total = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=conditions,
        params=params,
        idx=idx,
    )
    assert pid in ids


# ---------------------------------------------------------------------------
# execute_artifact_search
# ---------------------------------------------------------------------------


async def test_execute_empty_conditions(conn):
    """No conditions returns all artifacts (up to limit)."""
    pid = await _make_persona(conn)

    ids, _total = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=[],
        params=[],
        idx=1,
    )
    assert pid in ids


async def test_execute_limit_zero_returns_empty(conn):
    """limit_count=0 short-circuits to empty list."""
    await _make_persona(conn)

    result = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=[],
        params=[],
        idx=1,
        limit_count=0,
    )
    assert result == ([], 0)


async def test_execute_pagination(conn):
    """Limit and offset work correctly."""
    tag = _u()
    created = []
    for i in range(4):
        pid = await _make_persona(conn)
        nid = await _make_name(conn, f"pg-{tag}-{i:02d}")
        await _link_name(conn, pid, nid)
        created.append(pid)

    # Text filter to scope to just our 4
    conditions: list[str] = []
    params: list[object] = []
    idx = add_text_search(
        conditions,
        params,
        1,
        junction_table="persona_names_junction",
        owner_col="persona_id",
        resource_col="names_id",
        resource_table="names_resource",
        text_col="name",
        search=f"pg-{tag}",
    )

    order_join = (
        "LEFT JOIN persona_names_junction pnj ON pnj.persona_id = a.id AND pnj.active = true "
        "LEFT JOIN names_resource nr_sort ON nr_sort.id = pnj.names_id"
    )

    p1, _tc1 = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=list(conditions),
        params=list(params),
        idx=idx,
        order_join=order_join,
        order_expr="MIN(nr_sort.name) NULLS LAST",
        limit_count=2,
        offset_count=0,
    )
    p2, _tc2 = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=list(conditions),
        params=list(params),
        idx=idx,
        order_join=order_join,
        order_expr="MIN(nr_sort.name) NULLS LAST",
        limit_count=2,
        offset_count=2,
    )

    assert len(p1) == 2
    assert len(p2) == 2
    assert set(p1) & set(p2) == set()  # no overlap
    assert set(p1 + p2) == set(created)


async def test_execute_combined_filters(conn):
    """Multiple conditions (junction + text) combine with AND."""
    tag = _u()
    did = await _make_dept(conn)

    # Persona with both name and dept
    p1 = await _make_persona(conn)
    n1 = await _make_name(conn, f"combo-{tag}")
    await _link_name(conn, p1, n1)
    await _link_dept(conn, p1, did)

    # Persona with name but no dept
    p2 = await _make_persona(conn)
    n2 = await _make_name(conn, f"combo-{tag}-other")
    await _link_name(conn, p2, n2)

    # Persona with dept but wrong name
    p3 = await _make_persona(conn)
    n3 = await _make_name(conn, f"nope-{_u()}")
    await _link_name(conn, p3, n3)
    await _link_dept(conn, p3, did)

    conditions: list[str] = []
    params: list[object] = []
    idx = 1

    idx = add_text_search(
        conditions,
        params,
        idx,
        junction_table="persona_names_junction",
        owner_col="persona_id",
        resource_col="names_id",
        resource_table="names_resource",
        text_col="name",
        search=f"combo-{tag}",
    )
    idx = add_junction_filter(
        conditions,
        params,
        idx,
        junction_table="persona_departments_junction",
        owner_col="persona_id",
        resource_col="departments_id",
        ids=[did],
    )

    ids, _total = await execute_artifact_search(
        conn,
        table="persona_artifact",
        conditions=conditions,
        params=params,
        idx=idx,
    )
    assert p1 in ids
    assert p2 not in ids  # no dept
    assert p3 not in ids  # wrong name
