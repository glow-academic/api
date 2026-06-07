"""Regression: artifact create/update resolves department artifact IDs to resource IDs.

Observed (live probe): ``/rubric/create`` with a ``department_id`` taken from
``/department/search`` returns HTTP 500 — ``ForeignKeyViolationError`` on
``rubric_departments_junction.departments_id`` (FK ``departments_resource(id)``).
``/department/search`` surfaces the department *artifact* id, but every
``*_departments_junction.departments_id`` is FK'd to ``departments_resource``;
the create path wrote the artifact id verbatim → FK violation.

This is the #280/#282/#284 artifact-vs-resource id-space class, on the
cross-cutting ``department_ids`` dimension that the prior junction sweeps missed.

Mutation-verified against the real DB pool via black-box tools only (no raw SQL):
  * the shared resolver rewrites artifact→resource and passes unknown ids
    through (FAILS pre-fix only if the resolver did not exist — it is new);
  * ``resolve_rubric_values`` rewrites a department artifact id to its
    resource id on the item (FAILS pre-fix: artifact id passed straight through);
  * a full ``create_rubric_impl`` lands the *resource* id in the junction
    (FAILS pre-fix with the FK-violation 500);
  * the same rewrite holds across several other affected artifacts'
    ``resolve_*_values`` (FAILS pre-fix).
"""

from uuid import uuid4

import pytest

from app.infra.department_id_resolution import (
    resolve_department_ids_to_resource_ids,
)
from app.tools.artifacts.department.create import (
    create_department as create_department_artifact,
)
from app.tools.resources.departments.create import (
    create_department as create_department_resource,
)

pytestmark = pytest.mark.asyncio


async def _seed_department(pool, redis_client) -> tuple:
    """Seed a departments_resource + a department artifact linked to it.

    Returns ``(artifact_id, resource_id)`` — two distinct id-spaces. This mirrors
    what the system produces in practice: ``/department/search`` surfaces the
    artifact id, while ``*_departments_junction`` FKs to the resource id.
    """
    async with pool.acquire() as conn:
        resource = await create_department_resource(
            conn, name=f"dept-{uuid4().hex[:8]}", redis=redis_client
        )
        artifact = await create_department_artifact(
            conn, department_ids=[resource.id]
        )
    return artifact.id, resource.id


# ---------------------------------------------------------------------------
# Shared resolver
# ---------------------------------------------------------------------------


async def test_resolver_rewrites_artifact_to_resource(pool, redis_client):
    dept_a, dept_r = await _seed_department(pool, redis_client)
    assert dept_a != dept_r  # the two id-spaces genuinely differ

    async with pool.acquire() as conn:
        out = await resolve_department_ids_to_resource_ids(conn, [dept_a])

    assert out == [dept_r]
    assert dept_a not in out


async def test_resolver_passes_unknown_ids_through(pool, redis_client):
    # An already-resolved resource id (or any unknown id) must pass through
    # unchanged so the junction FK still validates.
    unknown = uuid4()
    async with pool.acquire() as conn:
        out = await resolve_department_ids_to_resource_ids(conn, [unknown])
    assert out == [unknown]


async def test_resolver_handles_resource_id_roundtrip(pool, redis_client):
    # A real resource id (round-tripped from a read side) is not a department
    # artifact id, so it passes through unchanged.
    _, dept_r = await _seed_department(pool, redis_client)
    async with pool.acquire() as conn:
        out = await resolve_department_ids_to_resource_ids(conn, [dept_r])
    assert out == [dept_r]


async def test_resolver_noops_on_empty(pool, redis_client):
    async with pool.acquire() as conn:
        assert await resolve_department_ids_to_resource_ids(conn, None) is None
        assert await resolve_department_ids_to_resource_ids(conn, []) == []


# ---------------------------------------------------------------------------
# resolve_rubric_values — the observed bug's resolution point
# ---------------------------------------------------------------------------


async def test_rubric_values_rewrites_department_artifact_id(pool, redis_client):
    from app.infra.rubric.permissions_context import resolve_rubric_values
    from app.infra.rubric.types import CreateRubricItem

    dept_a, dept_r = await _seed_department(pool, redis_client)

    item = CreateRubricItem(name="rub-xref", department_ids=[dept_a])
    async with pool.acquire() as conn:
        errors = await resolve_rubric_values(conn, redis_client, item, is_create=True)

    assert errors == []
    # The artifact id must be rewritten to its departments_resource id before
    # the junction write (FK target = departments_resource).
    assert item.department_ids == [dept_r]
    assert dept_a not in item.department_ids


# ---------------------------------------------------------------------------
# End-to-end junction write: artifact create lands the RESOURCE id
# ---------------------------------------------------------------------------


async def test_rubric_artifact_create_lands_resource_id_in_junction(
    pool, redis_client
):
    """Drive the resolved id through the artifact-create junction write (the
    write that raised the live FK-violation 500) and read it back via the
    black-box getter. Asserts the junction stores the RESOURCE id."""
    from app.infra.rubric.permissions_context import resolve_rubric_values
    from app.infra.rubric.types import CreateRubricItem
    from app.tools.artifacts.rubric.create import (
        create_rubric as create_rubric_artifact,
    )
    from app.tools.artifacts.rubric.get import get_rubrics as get_rubric_artifacts

    dept_a, dept_r = await _seed_department(pool, redis_client)

    item = CreateRubricItem(name=f"rub-{uuid4().hex[:8]}", department_ids=[dept_a])
    async with pool.acquire() as conn:
        # resolve (rewrites artifact->resource), then perform the real junction
        # write that previously violated the FK with the raw artifact id.
        await resolve_rubric_values(conn, redis_client, item, is_create=True)
        created = await create_rubric_artifact(
            conn, department_ids=item.department_ids
        )
        arts = await get_rubric_artifacts(conn, [created.id], departments=True)

    junction_dept_ids = list(arts[0].department_ids or [])
    assert dept_r in junction_dept_ids, (
        f"junction should store resource id {dept_r}, got {junction_dept_ids}"
    )
    assert dept_a not in junction_dept_ids


# ---------------------------------------------------------------------------
# Class coverage: the same rewrite across other affected artifacts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_path, resolve_name",
    [
        ("app.infra.eval.permissions_context", "resolve_eval_values"),
        ("app.infra.field.permissions_context", "resolve_field_values"),
        ("app.infra.parameter.permissions_context", "resolve_parameter_values"),
        ("app.infra.provider.permissions_context", "resolve_provider_values"),
        ("app.infra.setting.permissions_context", "resolve_setting_values"),
        ("app.infra.tool.permissions_context", "resolve_tool_values"),
    ],
)
async def test_other_artifacts_rewrite_department_ids(
    pool, redis_client, module_path, resolve_name
):
    """Each affected artifact's resolve_*_values rewrites a department artifact
    id to its resource id before the junction write (pre-fix: passed through →
    FK-violation 500 on create)."""
    import importlib

    mod = importlib.import_module(module_path)
    types_mod = importlib.import_module(
        module_path.replace("permissions_context", "types")
    )
    resolve = getattr(mod, resolve_name)
    # Each artifact's Create item class is f"Create{Artifact}Item".
    artifact = module_path.split(".")[2]
    CreateItem = getattr(types_mod, f"Create{artifact.capitalize()}Item")

    dept_a, dept_r = await _seed_department(pool, redis_client)
    item = CreateItem(name=f"{artifact}-xref", department_ids=[dept_a])
    async with pool.acquire() as conn:
        errors = await resolve(conn, redis_client, item, is_create=True)

    # We only assert the department resolution; other validation errors are
    # tolerated (some artifacts require more fields). The department_ids must be
    # rewritten regardless.
    assert item.department_ids == [dept_r], (
        f"{artifact}: expected [{dept_r}], got {item.department_ids} (errors={errors})"
    )
