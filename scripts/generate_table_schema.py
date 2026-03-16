#!/usr/bin/env python3
"""Generate a markdown file with all tables in the public schema."""

import asyncio

import asyncpg

DB_URL = "postgresql://myuser:mypassword@localhost:5432/mydb"


async def get_table_info():
    """Get all table information from the public schema."""
    conn = await asyncpg.connect(DB_URL)

    try:
        # Get all tables
        tables = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """)

        results = []

        for table in tables:
            table_name = table["tablename"]

            # Get all columns
            columns = await conn.fetch(
                """
                SELECT a.attname, a.attnum
                FROM pg_class c
                JOIN pg_attribute a ON a.attrelid = c.oid
                WHERE c.relname = $1
                    AND a.attnum > 0
                    AND NOT a.attisdropped
                ORDER BY a.attnum
            """,
                table_name,
            )

            all_cols = [col["attname"] for col in columns]

            # Get primary key columns
            pk_cols = await conn.fetch(
                """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = (SELECT oid FROM pg_class WHERE relname = $1)
                    AND i.indisprimary
                ORDER BY a.attnum
            """,
                table_name,
            )

            pk_names = [col["attname"] for col in pk_cols]

            # Get foreign key columns
            fk_cols = await conn.fetch(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = 'public'
                    AND tc.table_name = $1
                    AND tc.constraint_type = 'FOREIGN KEY'
                ORDER BY kcu.column_name
            """,
                table_name,
            )

            fk_names = [col["column_name"] for col in fk_cols]

            results.append(
                {
                    "name": table_name,
                    "pk": pk_names,
                    "fk": fk_names,
                    "all_cols": all_cols,
                }
            )

        return results

    finally:
        await conn.close()


def format_table_markdown(table_info):
    """Format table info as markdown."""
    name = table_info["name"]
    pk_cols = table_info["pk"]
    fk_cols = table_info["fk"]
    all_cols = table_info["all_cols"]

    # Build column list with formatting
    formatted_cols = []
    for col in all_cols:
        if col in pk_cols:
            formatted_cols.append(f"<u>{col}</u>")
        elif col in fk_cols:
            formatted_cols.append(f"*{col}*")
        else:
            formatted_cols.append(col)

    cols_str = ", ".join(formatted_cols)
    return f"{name}({cols_str})"


async def main():
    """Main function."""
    tables = await get_table_info()

    markdown_lines = []
    for table in tables:
        markdown_lines.append(format_table_markdown(table))

    print("\n".join(markdown_lines))


if __name__ == "__main__":
    asyncio.run(main())
