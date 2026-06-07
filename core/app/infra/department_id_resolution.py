"""Shared department artifact-ID → resource-ID resolution for junction writes.

Every artifact create/update accepts a ``department_ids`` field, and every
``*_departments_junction.departments_id`` column is FK'd to
``departments_resource(id)`` (the denormalized snapshot each department artifact
owns via its own ``department_departments_junction``).

But ``/department/search`` (and the department artifact search generally)
surfaces each row's id as the *department artifact* id — a different id-space
from ``departments_resource``. When a client takes a ``department_id`` straight
from ``/department/search`` and passes it as ``department_ids`` to any artifact
create/update, that artifact id is written verbatim into the junction, violating
the FK → ``ForeignKeyViolationError`` → HTTP 500.

This mirrors the #280/#282/#284 artifact-vs-resource id-space class. The prior
sweeps audited each artifact's *own* resource junctions but missed the shared,
cross-cutting ``department_ids`` dimension that all 16 artifacts accept.

Resolution uses the black-box ``get_departments`` artifact tool
(``departments=True`` hydrates each artifact's ``department_ids`` from its
self-junction, i.e. the snapshot ``departments_resource`` id). Unknown ids (e.g.
an already-resolved resource id round-tripped from a read side, or the
``departments`` CSV-name branch that already resolved to resource ids via
``search_departments`` over ``departments_resource``) pass through unchanged so
the FK still validates. No raw SQL.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from app.tools.artifacts.department.get import (
    get_departments as get_department_artifacts,
)


def _as_uuid(value: UUID | str) -> UUID | None:
    """Best-effort UUID coercion (some item types type ids as ``str``)."""
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


async def resolve_department_ids_to_resource_ids(
    conn: asyncpg.Connection,
    department_ids: list[UUID] | list[str] | None,
) -> list[UUID] | list[str] | None:
    """Map department *artifact* ids to their ``departments_resource`` ids.

    Returns the input unchanged (same identity) when ``department_ids`` is falsy.
    Ids that do not resolve to a department artifact (already-resolved resource
    ids, unknown ids) pass through unchanged so the junction FK still validates.

    Some item types declare ``department_ids`` as ``list[str]`` rather than
    ``list[UUID]``; both are accepted. The lookup is done on coerced UUIDs, and
    resolved ids are returned as ``UUID`` (which asyncpg accepts for the junction
    write); unresolved ids pass through with their original value/type.
    """
    if not department_ids:
        return department_ids

    coerced = [_as_uuid(did) for did in department_ids]
    lookup_ids = [u for u in coerced if u is not None]
    if not lookup_ids:
        return department_ids

    artifacts = await get_department_artifacts(
        conn, lookup_ids, departments=True
    )
    artifact_to_resource: dict[UUID, UUID] = {
        a.id: a.department_ids[0]
        for a in artifacts
        if a.id and a.department_ids
    }
    return [
        artifact_to_resource.get(u, original) if u is not None else original
        for original, u in zip(department_ids, coerced)
    ]
