"""In-image migration runner — replaces ``scripts/migrate-docker.sh``.

The bash script was host-side: it shelled out to ``docker compose exec database
psql`` and read .sql files from the host filesystem. That breaks when the
deploy CLI tries to invoke it from inside a container (no ``make``, no
Makefile, no docker socket).

This module runs *inside* the api image. It reads .sql files baked into the
image at ``/app/database/migrate/{add,remove}/`` and applies them via the
same DB connection the api uses. Same idempotency contract: each migration
is recorded in ``migrations.applied`` and skipped on subsequent runs.

Invocation:
  python -m database.scripts.migrate           # default: add
  python -m database.scripts.migrate add
  python -m database.scripts.migrate remove
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

import asyncpg  # type: ignore

# Two accepted conventions:
#   v<version>_<NN>_<description>.sql    e.g. v0.2.0_01_add_widget.sql
#   <YYYYMMDD>_<description>.sql         e.g. 20260520_add_operation_key_indexes.sql
# The version/number is just for ordering + dedup; either shape is fine.
_VERSIONED_RE = re.compile(r"^(v\d+\.\d+\.\d+)_(\d+)_.+\.sql$")
_DATED_RE = re.compile(r"^(\d{8})_.+\.sql$")

# Migrations live next to this script, baked into the image at
# `/app/database/migrate/` (see core/Dockerfile `COPY database/`).
_MIGRATE_ROOT = Path(__file__).resolve().parent.parent / "migrate"


async def _connect() -> asyncpg.Connection:
    """Connect via pgbouncer using the same env vars as the api itself.

    pgbouncer in session mode supports plain queries; we don't rely on
    prepared statements here so transaction mode would also work.
    """
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    host = os.environ.get("DB_HOST", "pgbouncer")
    port = int(os.environ.get("DB_PORT", "5432"))
    database = os.environ["DB_NAME"]
    return await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=database,
    )


async def _ensure_table(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE SCHEMA IF NOT EXISTS migrations;
        CREATE TABLE IF NOT EXISTS migrations.applied (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            version VARCHAR(20) NOT NULL,
            number INTEGER NOT NULL,
            type VARCHAR(10) NOT NULL DEFAULT 'add'
                CHECK (type IN ('add', 'remove')),
            name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT migrations_unique UNIQUE (version, number, type)
        );
        """
    )


async def _apply(mtype: str) -> None:
    mdir = _MIGRATE_ROOT / mtype
    if not mdir.is_dir():
        print(f"No {mtype} migration directory at {mdir}")
        return

    files = sorted(p for p in mdir.glob("*.sql") if p.name != "README.md")
    if not files:
        print(f"No {mtype} migration files in {mdir}")
        return

    conn = await _connect()
    try:
        await _ensure_table(conn)

        applied = 0
        skipped = 0
        # Track numbers handed out *this run* per version so two same-day dated
        # files processed in one pass don't both claim the same free number.
        assigned: dict[str, set[int]] = {}
        for sql_file in files:
            m_v = _VERSIONED_RE.match(sql_file.name)
            m_d = _DATED_RE.match(sql_file.name)
            if m_v:
                version = m_v.group(1)
                # Versioned filenames carry an explicit, per-version-unique
                # ordinal — honor it verbatim.
                number: int | None = int(m_v.group(2))
            elif m_d:
                # Dated filenames have no per-day ordinal; the number is
                # assigned dynamically below (after the dedup check) so that
                # multiple migrations sharing a date get DISTINCT numbers.
                version = m_d.group(1)
                number = None
            else:
                print(f"Skipping {sql_file.name} (unrecognized filename)")
                continue

            # Dedup on the migration's stable identity — its filename. The old
            # key was (version, number, type), but every dated file collapsed to
            # number=0, so the FIRST same-day migration to land permanently
            # shadowed every other one sharing that date (they matched the
            # already-applied (date, 0) row and were silently skipped forever).
            # `name` is unique per migration and is already recorded on every
            # existing instance, so this is backward-compatible: an already-
            # applied file is still recognized, a never-applied same-day file is
            # no longer falsely skipped.
            already = await conn.fetchval(
                """
                SELECT 1 FROM migrations.applied
                WHERE name=$1 AND type=$2
                """,
                sql_file.name, mtype,
            )
            if already:
                skipped += 1
                continue

            if number is None:
                # Smallest non-negative ordinal not already recorded for this
                # (version, type) and not handed out earlier in this run. On a
                # fresh DB the first same-day file gets 0, the next 1, ...; on an
                # existing instance the already-recorded same-day file keeps its
                # number (it's skipped above, never reassigned) and the new file
                # takes the next free slot — so we never collide with the
                # migrations_unique (version, number, type) constraint nor mutate
                # any row that's already there.
                used = {
                    r["number"]
                    for r in await conn.fetch(
                        """
                        SELECT number FROM migrations.applied
                        WHERE version=$1 AND type=$2
                        """,
                        version, mtype,
                    )
                }
                used |= assigned.get(version, set())
                number = 0
                while number in used:
                    number += 1

            print(f"Applying: {sql_file.name}")
            sql = sql_file.read_text()
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    """
                    INSERT INTO migrations.applied (version, number, type, name)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT DO NOTHING
                    """,
                    version, number, mtype, sql_file.name,
                )
            assigned.setdefault(version, set()).add(number)
            applied += 1

        print(f"{mtype} migrations: {applied} applied, {skipped} already applied")
    finally:
        await conn.close()


def main() -> None:
    mtype = sys.argv[1] if len(sys.argv) > 1 else "add"
    if mtype not in ("add", "remove"):
        print(f"Invalid migration type {mtype!r}; expected 'add' or 'remove'")
        sys.exit(2)
    asyncio.run(_apply(mtype))


if __name__ == "__main__":
    main()
