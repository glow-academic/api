"""Database connection and shared SQL queries for registry generation."""

from __future__ import annotations

import os
from collections import defaultdict

import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "mydb")
DB_USER = os.environ.get("DB_USER", "myuser")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "mypassword")


def get_connection():
    """Get a psycopg2 connection to the database."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def query_rows(cur, sql: str) -> list[tuple]:
    """Execute SQL and return all rows."""
    cur.execute(sql)
    return cur.fetchall()


def group_by_key(rows: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Group (key, value) rows into {key: sorted([values])}."""
    result: dict[str, set[str]] = defaultdict(set)
    for key, value in rows:
        result[key].add(value)
    return {k: sorted(v) for k, v in sorted(result.items())}


def invert_map(grouped: dict[str, list[str]]) -> dict[str, list[str]]:
    """Invert a grouped map: {k: [v1, v2]} → {v1: [k], v2: [k]}."""
    result: dict[str, set[str]] = defaultdict(set)
    for key, values in grouped.items():
        for v in values:
            result[v].add(key)
    return {k: sorted(v) for k, v in sorted(result.items())}
