"""PostgreSQL type → registry type string mapping."""

from __future__ import annotations

# PG data_type / udt_name → registry type string
PG_TYPE_MAP: dict[str, str] = {
    "uuid": "uuid",
    "text": "text",
    "character varying": "text",
    "boolean": "bool",
    "integer": "int",
    "smallint": "int",
    "bigint": "int",
    "int4": "int",
    "int2": "int",
    "int8": "int",
    "real": "float",
    "double precision": "float",
    "float4": "float",
    "float8": "float",
    "numeric": "numeric",
    "ARRAY": "array",
    "timestamp with time zone": "timestamp",
    "timestamptz": "timestamp",
    "timestamp without time zone": "timestamp",
    "USER-DEFINED": "enum",
    "jsonb": "text",
    "json": "text",
}

# System columns to exclude from resource/entry schemas
SYSTEM_COLUMNS: frozenset[str] = frozenset(
    {"id", "created_at", "active", "generated", "mcp"}
)


def pg_type_to_registry(data_type: str, udt_name: str) -> str:
    """Convert a PG column type to a registry type string."""
    # Check for array types first
    if data_type == "ARRAY":
        return "array"
    # Check data_type first, then udt_name
    if data_type in PG_TYPE_MAP:
        return PG_TYPE_MAP[data_type]
    if udt_name in PG_TYPE_MAP:
        return PG_TYPE_MAP[udt_name]
    # USER-DEFINED types (enums) have data_type='USER-DEFINED'
    return "enum"
