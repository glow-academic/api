"""Reusable junction table operations — upsert, deactivate, link.

All junction tables follow the pattern:
  {artifact}_{resource}_junction (owner_id, resource_id, active, created_at, generated, mcp)

These helpers work with any junction table regardless of artifact type.
"""

from uuid import UUID

import asyncpg


async def upsert_single(
    conn: asyncpg.Connection,
    *,
    table: str,
    owner_col: str,
    owner_id: UUID,
    resource_col: str,
    resource_id: UUID,
    constraint: str,
    generated: bool = False,
    mcp: bool = False,
    soft: bool = False,
) -> None:
    """Upsert a single-select junction row.

    Normal (soft=False): deactivates any existing active row with a different
    resource ID, then inserts or reactivates the target row.

    Soft (soft=True): inserts the new row as inactive without deactivating
    existing rows. Old values stay active until promoted.
    """
    if not soft:
        await conn.execute(
            f"UPDATE {table} SET active = false "
            f"WHERE {owner_col} = $1 AND active = true AND {resource_col} != $2",
            owner_id,
            resource_id,
        )
    is_active = not soft
    await conn.execute(
        f"INSERT INTO {table} ({owner_col}, {resource_col}, active, generated, mcp) VALUES ($1, $2, $3, $4, $5) "
        f"ON CONFLICT ON CONSTRAINT {constraint} "
        f"DO UPDATE SET {resource_col} = EXCLUDED.{resource_col}, active = EXCLUDED.active, generated = EXCLUDED.generated, mcp = EXCLUDED.mcp",
        owner_id,
        resource_id,
        is_active,
        generated,
        mcp,
    )


async def upsert_multi(
    conn: asyncpg.Connection,
    *,
    table: str,
    owner_col: str,
    owner_id: UUID,
    resource_col: str,
    resource_ids: list[UUID],
    constraint: str,
    generated: bool = False,
    mcp: bool = False,
    soft: bool = False,
) -> None:
    """Upsert multi-select junction rows.

    Normal (soft=False): deactivates rows whose resource ID is not in the new
    list, then inserts or reactivates rows for each ID in the list.
    Pass an empty list to deactivate all.

    Soft (soft=True): inserts new rows as inactive without deactivating
    existing rows. Old values stay active until promoted.
    """
    if not resource_ids:
        if not soft:
            await conn.execute(
                f"UPDATE {table} SET active = false "
                f"WHERE {owner_col} = $1 AND active = true",
                owner_id,
            )
        return

    if not soft:
        await conn.execute(
            f"UPDATE {table} SET active = false "
            f"WHERE {owner_col} = $1 AND active = true AND {resource_col} != ALL($2::uuid[])",
            owner_id,
            resource_ids,
        )
    is_active = not soft
    await conn.execute(
        f"INSERT INTO {table} ({owner_col}, {resource_col}, active, generated, mcp) "
        f"SELECT $1, unnest($2::uuid[]), $3, $4, $5 "
        f"ON CONFLICT ON CONSTRAINT {constraint} "
        f"DO UPDATE SET active = EXCLUDED.active, generated = EXCLUDED.generated, mcp = EXCLUDED.mcp",
        owner_id,
        resource_ids,
        is_active,
        generated,
        mcp,
    )


async def insert_single(
    conn: asyncpg.Connection,
    *,
    table: str,
    owner_col: str,
    owner_id: UUID,
    resource_col: str,
    resource_id: UUID,
    generated: bool = False,
    mcp: bool = False,
) -> None:
    """Insert a single junction row (for create, not update)."""
    await conn.execute(
        f"INSERT INTO {table} ({owner_col}, {resource_col}, generated, mcp) "
        f"VALUES ($1, $2, $3, $4)",
        owner_id,
        resource_id,
        generated,
        mcp,
    )


async def insert_multi(
    conn: asyncpg.Connection,
    *,
    table: str,
    owner_col: str,
    owner_id: UUID,
    resource_col: str,
    resource_ids: list[UUID],
    generated: bool = False,
    mcp: bool = False,
) -> None:
    """Insert multiple junction rows (for create, not update)."""
    if not resource_ids:
        return
    await conn.executemany(
        f"INSERT INTO {table} ({owner_col}, {resource_col}, generated, mcp) "
        f"VALUES ($1, $2, $3, $4)",
        [(owner_id, rid, generated, mcp) for rid in resource_ids],
    )


async def delete_junctions_by_owner(
    conn: asyncpg.Connection,
    *,
    tables: list[str],
    owner_col: str,
    owner_ids: list[UUID],
) -> None:
    """Hard-delete every junction row owned by the given artifact ids.

    Most ``{artifact}_*_junction`` tables declare their owner-side FK with
    ``ON DELETE CASCADE``, so a hard DELETE of the artifact tears the
    junction rows down automatically. A handful of junctions were created
    *without* that cascade (NO ACTION default), which makes a hard delete of
    a populated artifact fail with a foreign_key_violation. This helper lets
    an artifact delete tool clear those non-cascading junctions explicitly
    *before* deleting the artifact, restoring the "junctions cascade"
    contract the delete tools promise.
    """
    if not owner_ids or not tables:
        return
    for table in tables:
        await conn.execute(
            f"DELETE FROM {table} WHERE {owner_col} = ANY($1)",
            owner_ids,
        )
