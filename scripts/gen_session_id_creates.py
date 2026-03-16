#!/usr/bin/env python3
"""Generate internal-only create functions for 19 session_id entries.

For each entry, generates:
1. SQL: Strongly-typed INSERT function (replaces generic wrapper)
2. types.py: Appends Create*SqlParams, Create*SqlRow, Create*Response
3. create.py: Internal-only async function (no HTTP route)
"""

import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(BASE, "server/app/sql/v4/queries/entries")
PY_DIR = os.path.join(BASE, "server/app/api/v4/entries")

# ── Entry definitions ────────────────────────────────────────────────────────
# Each entry: (name, [(param_name, sql_type, python_type, default_sql, default_py), ...], special_flags)

ENTRIES = [
    # ── Simple (session_id only) ──
    ("activity", [], {}),
    ("logins", [], {}),
    (
        "sessions",
        [
            ("profile_id", "uuid", "UUID", None, None),
        ],
        {},
    ),
    # ── Media ──
    (
        "audios",
        [
            ("upload_id", "uuid", "UUID | None", "DEFAULT NULL", "None"),
            ("message_id", "uuid", "UUID | None", "DEFAULT NULL", "None"),
            ("length_seconds", "integer", "int", "DEFAULT 0", "0"),
        ],
        {},
    ),
    (
        "images",
        [
            ("upload_id", "uuid", "UUID | None", "DEFAULT NULL", "None"),
            ("message_id", "uuid", "UUID | None", "DEFAULT NULL", "None"),
        ],
        {},
    ),
    (
        "videos",
        [
            ("upload_id", "uuid", "UUID | None", "DEFAULT NULL", "None"),
            ("message_id", "uuid", "UUID | None", "DEFAULT NULL", "None"),
            ("length_seconds", "integer", "int", "DEFAULT 0", "0"),
        ],
        {},
    ),
    # ── Infrastructure ──
    (
        "audits",
        [
            ("message", "text", "str", None, None),
            ("endpoint", "text", "str", None, None),
            ("error", "boolean", "bool", "DEFAULT false", "False"),
        ],
        {},
    ),
    (
        "calls",
        [
            ("external_call_id", "text", "str", None, None),
            ("run_id", "uuid", "UUID | None", "DEFAULT NULL", "None"),
        ],
        {},
    ),
    (
        "emulations",
        [
            ("grant_id", "uuid", "UUID", None, None),
        ],
        {},
    ),
    (
        "grants",
        [
            ("expires_at", "timestamptz", "str", None, None),
        ],
        {},
    ),
    (
        "groups",
        [
            ("name", "text", "str | None", "DEFAULT NULL", "None"),
            ("custom_model", "boolean", "bool", "DEFAULT false", "False"),
        ],
        {},
    ),
    (
        "messages_completions",
        [
            ("message_id", "uuid", "UUID", None, None),
        ],
        {},
    ),
    (
        "metrics",
        [
            ("ts", "timestamptz", "str", None, None),
            ("requests_total", "bigint", "int", None, None),
            ("errors_total", "bigint", "int", None, None),
            ("avg_latency_ms", "double precision", "float", None, None),
            ("cpu_percent", "double precision", "float", None, None),
            ("memory_bytes", "bigint", "int", None, None),
        ],
        {"no_id": True},
    ),
    (
        "run_pricing",
        [
            ("pricing_type", "pricing_type", "str", None, None),
            ("count", "integer", "int", "DEFAULT 0", "0"),
            ("run_id", "uuid", "UUID", None, None),
        ],
        {},
    ),
    (
        "runs",
        [
            ("group_id", "uuid", "UUID | None", "DEFAULT NULL", "None"),
        ],
        {},
    ),
    (
        "texts",
        [
            ("content", "text", "str", None, None),
        ],
        {"dedup": True},
    ),
    (
        "tokens",
        [
            ("run_id", "uuid", "UUID", None, None),
            ("input_tokens", "integer", "int", "DEFAULT 0", "0"),
            ("output_tokens", "integer", "int", "DEFAULT 0", "0"),
            ("cached_input_tokens", "integer", "int", "DEFAULT 0", "0"),
        ],
        {},
    ),
    (
        "uploads",
        [
            ("file_path", "text", "str", None, None),
            ("mime_type", "text", "str", None, None),
            ("size", "bigint", "int", None, None),
        ],
        {},
    ),
    (
        "uploads_completions",
        [
            ("upload_id", "uuid", "UUID", None, None),
            ("end_reason", "text", "str", "DEFAULT ''", "''"),
        ],
        {},
    ),
]


def to_pascal(name: str) -> str:
    return "".join(w.capitalize() for w in name.split("_"))


# ── SQL Generation ───────────────────────────────────────────────────────────


def gen_sql(name: str, params: list, flags: dict) -> str:
    func_name = f"api_create_{name}_entry_v4"
    is_dedup = flags.get("dedup", False)
    is_no_id = flags.get("no_id", False)

    # Build parameter list
    sql_params = ["    session_id uuid"]
    for pname, ptype, _, default_sql, _ in params:
        line = f"    {pname} {ptype}"
        if default_sql:
            line += f" {default_sql}"
        sql_params.append(line)
    sql_params.append("    mcp boolean DEFAULT false")
    params_str = ",\n".join(sql_params)

    # Return type
    if is_no_id:
        return_type = "TABLE (ts text)"
    else:
        return_type = "TABLE (id uuid)"

    # INSERT columns and values
    insert_cols = ["session_id"]
    insert_vals = [f"{func_name}.session_id"]
    for pname, _, _, _, _ in params:
        insert_cols.append(pname)
        insert_vals.append(f"{func_name}.{pname}")
    insert_cols.append("mcp")
    insert_vals.append(f"{func_name}.mcp")

    cols_str = ", ".join(insert_cols)
    vals_str = ", ".join(insert_vals)

    # Function body
    if is_dedup:
        body = f"""DECLARE v_id uuid;
BEGIN
    INSERT INTO {name}_entry ({cols_str}, generated)
    VALUES ({vals_str}, true)
    ON CONFLICT (content_hash) DO UPDATE SET id = {name}_entry.id
    RETURNING {name}_entry.id INTO v_id;
    RETURN QUERY SELECT v_id;
END;"""
    elif is_no_id:
        body = f"""DECLARE v_ts text;
BEGIN
    INSERT INTO {name}_entry ({cols_str})
    VALUES ({vals_str})
    RETURNING {name}_entry.ts::text INTO v_ts;
    RETURN QUERY SELECT v_ts;
END;"""
    else:
        body = f"""DECLARE v_id uuid;
BEGIN
    INSERT INTO {name}_entry ({cols_str}, generated)
    VALUES ({vals_str}, true)
    RETURNING {name}_entry.id INTO v_id;
    RETURN QUERY SELECT v_id;
END;"""

    return f"""-- Create {name} entry with strongly-typed params

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT oidvectortypes(proargtypes) AS sig
        FROM pg_proc
        WHERE proname = '{func_name}'
          AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    LOOP
        EXECUTE format('DROP FUNCTION IF EXISTS {func_name}(%s)', r.sig);
    END LOOP;
END $$;

CREATE OR REPLACE FUNCTION public.{func_name}(
{params_str}
) RETURNS {return_type}
LANGUAGE plpgsql AS $$
{body} $$;
"""


# ── Python types.py additions ────────────────────────────────────────────────


def gen_types_additions(name: str, params: list, flags: dict) -> str:
    pascal = to_pascal(name)
    is_no_id = flags.get("no_id", False)

    lines = []
    lines.append("")
    lines.append("")
    lines.append(f"class Create{pascal}EntrySqlParams(BaseModel):")
    lines.append("    session_id: UUID")
    for pname, _, pytype, _, pydefault in params:
        line = f"    {pname}: {pytype}"
        if pydefault is not None:
            line += f" = {pydefault}"
        lines.append(line)
    lines.append("    mcp: bool = False")
    lines.append("")
    lines.append("    def to_tuple(self) -> tuple:")
    tuple_fields = ["self.session_id"]
    for pname, _, _, _, _ in params:
        tuple_fields.append(f"self.{pname}")
    tuple_fields.append("self.mcp")
    if len(tuple_fields) <= 3:
        lines.append(f"        return ({', '.join(tuple_fields)},)")
    else:
        lines.append("        return (")
        for f in tuple_fields:
            lines.append(f"            {f},")
        lines.append("        )")

    lines.append("")
    lines.append("")
    lines.append(f"class Create{pascal}EntrySqlRow(BaseModel):")
    if is_no_id:
        lines.append("    ts: str")
    else:
        lines.append("    id: UUID")

    lines.append("")
    lines.append("")
    lines.append(f"class Create{pascal}EntryResponse(BaseModel):")
    if is_no_id:
        lines.append("    ts: str")
    else:
        lines.append("    id: UUID")
    lines.append("")

    return "\n".join(lines)


# ── Python create.py ─────────────────────────────────────────────────────────


def gen_create_py(name: str, params: list, flags: dict) -> str:
    pascal = to_pascal(name)
    is_no_id = flags.get("no_id", False)

    # Function signature params
    func_params = ["    conn: asyncpg.Connection,", "    session_id: UUID,"]
    for pname, _, pytype, _, pydefault in params:
        line = f"    {pname}: {pytype}"
        if pydefault is not None:
            line += f" = {pydefault}"
        line += ","
        func_params.append(line)
    func_params.append("    mcp: bool = False,")
    func_params_str = "\n".join(func_params)

    # Params constructor kwargs
    kwargs = ["session_id=session_id"]
    for pname, _, _, _, _ in params:
        kwargs.append(f"{pname}={pname}")
    kwargs.append("mcp=mcp")
    kwargs_str = ", ".join(kwargs)

    result_field = "ts" if is_no_id else "id"

    return f'''"""Internal {name} entry create — no HTTP route."""

from typing import cast
from uuid import UUID

import asyncpg  # type: ignore

from app.api.v4.entries.{name}.types import (
    Create{pascal}EntryResponse,
    Create{pascal}EntrySqlParams,
    Create{pascal}EntrySqlRow,
)
from app.utils.sql_helper import execute_sql_typed

SQL_PATH = "app/sql/v4/queries/entries/{name}/create_{name}_entries_complete.sql"


async def create_{name}_entry_internal(
{func_params_str}
) -> Create{pascal}EntryResponse:
    """Create a {name} entry. Internal only — no HTTP route."""
    params = Create{pascal}EntrySqlParams({kwargs_str})

    result = cast(
        Create{pascal}EntrySqlRow,
        await execute_sql_typed(conn, SQL_PATH, params=params),
    )

    if not result or not result.{result_field}:
        raise ValueError("Failed to create {name} entry")

    return Create{pascal}EntryResponse.model_validate(result.model_dump())
'''


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    for name, params, flags in ENTRIES:
        print(f"Generating {name}...")

        # 1. Write SQL
        sql_path = os.path.join(SQL_DIR, name, f"create_{name}_entries_complete.sql")
        os.makedirs(os.path.dirname(sql_path), exist_ok=True)
        with open(sql_path, "w") as f:
            f.write(gen_sql(name, params, flags))

        # 2. Append to types.py
        types_path = os.path.join(PY_DIR, name, "types.py")
        existing = open(types_path).read()

        if f"Create{to_pascal(name)}EntrySqlParams" in existing:
            print("  types.py already has Create types, skipping")
        else:
            if "from uuid import UUID" not in existing:
                existing = existing.replace(
                    "from pydantic import BaseModel",
                    "from uuid import UUID\n\nfrom pydantic import BaseModel",
                )
                with open(types_path, "w") as f:
                    f.write(existing)

            additions = gen_types_additions(name, params, flags)
            with open(types_path, "a") as f:
                f.write(additions)

        # 3. Write create.py
        create_path = os.path.join(PY_DIR, name, "create.py")
        with open(create_path, "w") as f:
            f.write(gen_create_py(name, params, flags))

    print(f"\nDone! Generated files for {len(ENTRIES)} entries.")


if __name__ == "__main__":
    main()
