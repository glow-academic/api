"""Tests for infra.search.search_artifact — shared SQL-builder helpers.

Uses persona_* tables as a concrete test bed, but the helpers
themselves are artifact-agnostic.
"""

import pytest

from app.infra.search.search_artifact import (
    add_junction_filter,
    add_text_search,
    execute_artifact_search,
)
from app.infra.shared_types import MAX_SEARCH_LIMIT
from tests.helpers import unique_tag


class _RecordingConn:
    """Minimal asyncpg.Connection stand-in that records the LIMIT/OFFSET
    bind params the query was executed with (no DB round-trip)."""

    def __init__(self) -> None:
        self.last_args: tuple = ()

    async def fetch(self, _query: str, *args: object):
        self.last_args = args
        return []

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


async def test_execute_clamps_oversized_limit():
    """A non-model code path requesting a huge LIMIT is clamped to
    MAX_SEARCH_LIMIT (defense-in-depth against a full-table-scan / OOM DoS)."""
    rc = _RecordingConn()
    await execute_artifact_search(
        rc,  # type: ignore[arg-type]
        table="persona_artifact",
        conditions=[],
        params=[],
        idx=1,
        limit_count=10_000_000,
    )
    # Last two bind params are (limit, offset). Limit must be clamped.
    assert rc.last_args[-2] == MAX_SEARCH_LIMIT
    assert rc.last_args[-1] == 0


async def test_execute_preserves_within_bound_limit():
    """A limit within the ceiling is passed through unchanged."""
    rc = _RecordingConn()
    await execute_artifact_search(
        rc,  # type: ignore[arg-type]
        table="persona_artifact",
        conditions=[],
        params=[],
        idx=1,
        limit_count=25,
        offset_count=5,
    )
    assert rc.last_args[-2] == 25
    assert rc.last_args[-1] == 5


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


async def test_execute_pagination_tied_names_no_dup_or_skip(conn):
    """P2: artifacts with IDENTICAL sort names must paginate without dup/skip.

    ``MIN(nr_sort.name)`` is non-unique; without the ``a.id`` tiebreaker the
    LIMIT/OFFSET order is arbitrary and a row can land on two pages or none.
    All six personas share the same name → the order is decided purely by the
    appended ``a.id`` tiebreaker."""
    tag = _u()
    same_name = f"tie-{tag}"  # identical sort key for every persona
    # names_resource.name is UNIQUE — link ALL personas to the SAME name row so
    # MIN(nr_sort.name) is identical (tied) across all six.
    nid = await _make_name(conn, same_name)
    created = []
    for _ in range(6):
        pid = await _make_persona(conn)
        await _link_name(conn, pid, nid)
        created.append(pid)

    conditions: list[str] = []
    params: list[object] = []
    idx = add_text_search(
        conditions, params, 1,
        junction_table="persona_names_junction",
        owner_col="persona_id", resource_col="names_id",
        resource_table="names_resource", text_col="name", search=same_name,
    )
    order_join = (
        "LEFT JOIN persona_names_junction pnj ON pnj.persona_id = a.id AND pnj.active = true "
        "LEFT JOIN names_resource nr_sort ON nr_sort.id = pnj.names_id"
    )

    pages = []
    for off in (0, 2, 4):
        page, _tc = await execute_artifact_search(
            conn, table="persona_artifact",
            conditions=list(conditions), params=list(params), idx=idx,
            order_join=order_join, order_expr="MIN(nr_sort.name) NULLS LAST",
            limit_count=2, offset_count=off,
        )
        pages.append(page)

    flat = [pid for page in pages for pid in page]
    assert len(flat) == 6
    assert set(flat) == set(created)  # no skips
    assert len(set(flat)) == 6  # no dups across pages


async def test_execute_pagination_deterministic_across_calls(conn):
    """P2: the same paged query returns the SAME row on repeated calls — the
    ``a.id`` tiebreaker makes the total order stable for tied/NULL sort keys.
    (NULL names exercise the NULLS LAST + tiebreaker path.)"""
    tag = _u()
    created = []
    for _ in range(5):
        pid = await _make_persona(conn)
        # No name linked → MIN(nr_sort.name) is NULL for all five (tied NULLs).
        created.append(pid)

    # Scope to just our 5 via a department junction filter.
    did = await _make_dept(conn)
    for pid in created:
        await _link_dept(conn, pid, did)

    order_join = (
        "LEFT JOIN persona_names_junction pnj ON pnj.persona_id = a.id AND pnj.active = true "
        "LEFT JOIN names_resource nr_sort ON nr_sort.id = pnj.names_id"
    )

    def _query():
        conditions: list[str] = []
        params: list[object] = []
        idx = add_junction_filter(
            conditions, params, 1,
            junction_table="persona_departments_junction",
            owner_col="persona_id", resource_col="departments_id", ids=[did],
        )
        return conditions, params, idx

    async def _page(off):
        conditions, params, idx = _query()
        page, _tc = await execute_artifact_search(
            conn, table="persona_artifact",
            conditions=conditions, params=params, idx=idx,
            order_join=order_join, order_expr="MIN(nr_sort.name) NULLS LAST",
            limit_count=2, offset_count=off,
        )
        return page

    # Same offset, called twice → identical (deterministic) result.
    assert await _page(0) == await _page(0)
    assert await _page(2) == await _page(2)

    # And the full walk covers every row exactly once.
    flat = (await _page(0)) + (await _page(2)) + (await _page(4))
    assert set(flat) == set(created)
    assert len(set(flat)) == 5


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
