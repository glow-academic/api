"""Pull table columns from Postgres information_schema."""

import asyncpg  # type: ignore

from app.infra.docs.types import ColumnInfo, TableInfo


async def get_table_info(conn: asyncpg.Connection, table_name: str) -> TableInfo | None:
    """Get table columns. Returns None if table does not exist."""
    cols = await conn.fetch(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = $1
        ORDER BY ordinal_position
        """,
        table_name,
    )

    if not cols:
        return None

    return TableInfo(
        name=table_name,
        columns=[
            ColumnInfo(
                name=c["column_name"],
                type=c["data_type"],
                nullable=c["is_nullable"] == "YES",
            )
            for c in cols
        ],
    )
