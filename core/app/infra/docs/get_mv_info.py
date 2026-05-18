"""Pull materialized view definition + columns from Postgres catalog."""

import asyncpg  # type: ignore

from app.infra.docs.types import ColumnInfo, MvInfo


async def get_mv_info(conn: asyncpg.Connection, mv_name: str) -> MvInfo | None:
    """Get MV definition and columns. Returns None if MV does not exist."""
    definition = await conn.fetchval(
        "SELECT definition FROM pg_matviews WHERE matviewname = $1",
        mv_name,
    )

    if definition is None:
        return None

    cols = await conn.fetch(
        """
        SELECT a.attname AS column_name,
               pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
               NOT a.attnotnull AS nullable
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        WHERE c.relname = $1
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY a.attnum
        """,
        mv_name,
    )

    return MvInfo(
        name=mv_name,
        definition=definition.strip().rstrip(";"),
        columns=[
            ColumnInfo(
                name=c["column_name"],
                type=c["data_type"],
                nullable=c["nullable"],
            )
            for c in cols
        ],
    )
