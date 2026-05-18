"""SQL introspection engine for type generation.

Uses asyncpg to PREPARE queries and extract parameter/return types,
mapping Postgres OIDs to Python types.
"""

from dataclasses import dataclass
from typing import Any

import asyncpg  # type: ignore

from app.utils.sql_helper import load_sql

# Postgres type OIDs to Python type mapping
# Common OIDs from PostgreSQL documentation
OID_TO_PYTHON_TYPE: dict[int, str] = {
    # Boolean
    16: "bool",  # BOOLEAN
    # Integer types
    20: "int",  # BIGINT
    21: "int",  # SMALLINT
    23: "int",  # INTEGER
    # Float types
    700: "float",  # REAL (FLOAT4)
    701: "float",  # DOUBLE PRECISION (FLOAT8)
    1700: "float",  # NUMERIC
    # Text types
    25: "str",  # TEXT
    1043: "str",  # VARCHAR
    1042: "str",  # CHAR
    # UUID - use uuid.UUID for strong typing
    2950: "UUID",  # UUID (use uuid.UUID for strong typing)
    2951: "list[UUID]",  # UUID[] (use list[uuid.UUID] for strong typing)
    # Timestamp types
    1114: "datetime",  # TIMESTAMP
    1184: "datetime",  # TIMESTAMPTZ
    1082: "date",  # DATE
    1083: "time",  # TIME
    1266: "time",  # TIMETZ
    # JSON types
    114: "Any",  # JSON can be dict or list
    3802: "Any",  # JSONB can be dict or list
    # Array types (base OID + 1 = array OID)
    # We'll detect arrays by checking if OID is in pg_type with typarray
    1000: "list[bool]",  # BOOLEAN[]
    1001: "list[bytes]",  # BYTEA[]
    1002: "list[str]",  # CHAR[]
    1003: "list[str]",  # NAME[]
    1005: "list[int]",  # SMALLINT[]
    1006: "list[int]",  # OID[]
    1007: "list[int]",  # INTEGER[]
    1009: "list[str]",  # TEXT[]
    1014: "list[str]",  # BPCHAR[]
    1015: "list[str]",  # VARCHAR[]
    1016: "list[int]",  # BIGINT[]
    1021: "list[float]",  # FLOAT4[]
    1022: "list[float]",  # FLOAT8[]
    1028: "list[int]",  # INT4[]
    1033: "list[str]",  # ACLITEM[]
    1034: "list[UUID]",  # UUID[] (use list[uuid.UUID] for strong typing)
    1115: "list[datetime]",  # TIMESTAMP[]
    1182: "list[date]",  # DATE[]
    1183: "list[time]",  # TIME[]
    1185: "list[datetime]",  # TIMESTAMPTZ[]
    1186: "list[timedelta]",  # INTERVAL[]
    1187: "list[time]",  # TIMETZ[]
    199: "list[dict[str, Any]]",  # JSON[]
    3807: "list[dict[str, Any]]",  # JSONB[]
}


@dataclass
class ColumnMetadata:
    """Metadata for a single column."""

    name: str
    python_type: str
    pg_oid: int
    is_array: bool
    is_optional: bool = False  # For parameters: whether field is optional (nullable)
    default_value: str | None = (
        None  # For parameters: default value expression (e.g., "[]", "None")
    )


@dataclass
class SQLMetadata:
    """Metadata extracted from a SQL file."""

    sql_path: str
    parameters: list[ColumnMetadata]  # Ordered $1, $2, ...
    returns: list[ColumnMetadata]  # Return columns
    error: str | None = None  # If introspection failed


def _parse_atparams_block(sql_text: str) -> dict[int, dict[str, Any]]:
    """Parse @params block for parameter metadata.

    Parses:
    -- @params
    --   name: text
    --   prompt_id?: uuid
    --   department_ids: uuid[] = {}

    Returns dict mapping param index to {name, type, optional, default}
    """
    import re

    param_metadata: dict[int, dict[str, Any]] = {}

    # Find @params block
    atparams_pattern = r"--\s*@params\s*\n((?:--\s+.*\n)*)"
    match = re.search(atparams_pattern, sql_text, re.IGNORECASE | re.MULTILINE)

    if not match:
        return param_metadata

    params_block = match.group(1)

    # Extract parameter definitions: name: type, name?: type, name: type = default
    param_line_pattern = r"--\s+(\w+)(\?)?:\s+(\S+)(?:\s*=\s*(.+))?"

    param_index = 1
    for line_match in re.finditer(param_line_pattern, params_block, re.IGNORECASE):
        param_name = line_match.group(1)
        is_optional = line_match.group(2) == "?"
        param_type = line_match.group(3)
        default_value = line_match.group(4) if line_match.group(4) else None

        param_metadata[param_index] = {
            "name": param_name,
            "type": param_type,
            "optional": is_optional,
            "default": default_value,
        }
        param_index += 1

    return param_metadata


def _extract_param_names_from_params_cte(sql_text: str) -> dict[int, str]:
    """Extract parameter names from params CTE column aliases or comments.

    First tries to extract from params CTE pattern: WITH params AS (SELECT $1::type AS name, ...)
    Falls back to parsing comments: -- Parameters: $1=name (type), $2=name2 (type), ...

    Args:
        sql_text: SQL query text

    Returns:
        Dict mapping parameter index to name (e.g., {1: "name", 2: "description"})
    """
    import re

    param_names: dict[int, str] = {}

    # First, try to extract from params CTE
    params_cte_pattern = r"WITH\s+params\s+AS\s*\(\s*SELECT\s+(.*?)\s*\)\s*,"
    match = re.search(params_cte_pattern, sql_text, re.IGNORECASE | re.DOTALL)

    if match:
        select_clause = match.group(1)

        # Split by commas to get individual column definitions
        # But be careful of commas inside function calls
        columns = []
        current_col = ""
        paren_depth = 0
        for char in select_clause:
            if char == "(":
                paren_depth += 1
                current_col += char
            elif char == ")":
                paren_depth -= 1
                current_col += char
            elif char == "," and paren_depth == 0:
                columns.append(current_col.strip())
                current_col = ""
            else:
                current_col += char
        if current_col.strip():
            columns.append(current_col.strip())

        # Extract parameter number and alias from each column
        for col in columns:
            # Find the AS keyword and extract the alias
            as_match = re.search(r"\s+AS\s+(\w+)", col, re.IGNORECASE)
            if not as_match:
                continue

            param_name = as_match.group(1)

            # Find the parameter number ($N)
            param_match = re.search(r"\$(\d+)", col)
            if param_match:
                param_index = int(param_match.group(1))
                param_names[param_index] = param_name

    # If no params CTE found, try parsing from comments
    if not param_names:
        # Pattern: -- Parameters: $1=name (type), $2=name2 (type), ...
        comment_pattern = r"--\s*Parameters?:\s*(.*?)(?:\n|$)"
        comment_match = re.search(
            comment_pattern, sql_text, re.IGNORECASE | re.MULTILINE
        )
        if comment_match:
            params_line = comment_match.group(1)
            # Extract $N=name patterns
            param_pattern = r"\$(\d+)\s*=\s*(\w+)"
            for param_match in re.finditer(param_pattern, params_line):
                param_index = int(param_match.group(1))
                param_name = param_match.group(2)
                param_names[param_index] = param_name

    return param_names


def _detect_nullable_columns(sql_text: str, column_names: list[str]) -> set[str]:
    """Detect columns that can be NULL based on SQL patterns.

    Checks for:
    1. COALESCE(column, NULL) patterns - redundant COALESCE that still allows NULL
    2. LEFT JOIN patterns - columns from LEFT JOINed tables can be NULL

    Args:
        sql_text: SQL query text
        column_names: List of column names from introspection

    Returns:
        Set of column names that are nullable
    """
    nullable_columns: set[str] = set()
    sql_upper = sql_text.upper()

    # Pattern 1: Detect COALESCE(..., NULL) patterns
    # This is redundant and indicates the field can be NULL
    import re

    # Match: COALESCE(column, NULL) or COALESCE(alias.column, NULL) ... AS column_name
    # Look for the full pattern including the AS clause to match column names accurately
    coalesce_null_pattern = (
        r"COALESCE\s*\(\s*([\w.]+)\s*,\s*NULL\s*\)[^,]*?\s+AS\s+(\w+)"
    )
    matches = re.finditer(coalesce_null_pattern, sql_text, re.IGNORECASE)
    for match in matches:
        # Extract the column name from the AS clause
        as_column_name = match.group(2).lower()
        # Check if this matches any of our column names
        for col_name in column_names:
            if as_column_name == col_name.lower():
                nullable_columns.add(col_name)
                break

    # Also check for COALESCE patterns without explicit AS (fallback)
    # Match: COALESCE(column, NULL) or COALESCE(alias.column, NULL)
    coalesce_null_pattern_fallback = r"COALESCE\s*\(\s*([\w.]+)\s*,\s*NULL\s*\)"
    matches_fallback = re.finditer(
        coalesce_null_pattern_fallback, sql_upper, re.IGNORECASE
    )
    for match in matches_fallback:
        # Extract column reference (could be alias.column or just column)
        column_ref = match.group(1).lower()
        # Try to match against column names (handle aliases)
        for col_name in column_names:
            # Check if column_ref matches the column name or ends with it
            if column_ref == col_name.lower() or column_ref.endswith(
                "." + col_name.lower()
            ):
                nullable_columns.add(col_name)

    # Pattern 2: Detect LEFT JOIN patterns
    # Find all LEFT JOINs and extract table aliases
    left_join_pattern = r"LEFT\s+JOIN\s+[\w.]+\s+(\w+)"
    left_join_matches = re.finditer(left_join_pattern, sql_upper, re.IGNORECASE)
    left_join_aliases: set[str] = set()
    for match in left_join_matches:
        alias = match.group(1).lower()
        left_join_aliases.add(alias)

    # Check if columns come from LEFT JOINed tables
    # Look for column references like alias.column in SELECT clause
    select_pattern = r"SELECT\s+(.*?)(?:\s+FROM|\s+WHERE|\s+ORDER|\s+GROUP|\Z)"
    select_match = re.search(select_pattern, sql_text, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_clause = select_match.group(1)
        # Find column references with aliases
        for col_name in column_names:
            # Look for patterns like "alias.column AS column_name" or "alias.column::type AS column_name"
            # Also check for direct references in COALESCE
            col_ref_pattern = rf"(\w+)\.{re.escape(col_name.lower())}"
            col_matches = re.finditer(col_ref_pattern, select_clause, re.IGNORECASE)
            for col_match in col_matches:
                alias = col_match.group(1).lower()
                if alias in left_join_aliases:
                    nullable_columns.add(col_name)

    return nullable_columns


async def fetch_composite_fields(
    conn: asyncpg.Connection, full_type_name: str
) -> list[tuple[str, str, bool]]:
    """Fetch fields from a composite type.

    Args:
        conn: Database connection
        full_type_name: Full type name (e.g., 'types.q_list_agents_v3_agent')

    Returns:
        List of (field_name, pg_type, not_null) tuples
    """
    rows = await conn.fetch(
        """
        SELECT
          a.attname as field_name,
          format_type(a.atttypid, a.atttypmod) as pg_type,
          a.attnotnull as not_null
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_attribute a ON a.attrelid = t.typrelid
        WHERE (n.nspname || '.' || t.typname) = $1
          AND a.attnum > 0
          AND not a.attisdropped
        ORDER BY a.attnum;
        """,
        full_type_name,
    )
    return [(r["field_name"], r["pg_type"], r["not_null"]) for r in rows]


async def fetch_function_inputs(
    conn: asyncpg.Connection,
    function_name: str,
    schema: str = "public",
    function_oid: int | None = None,
) -> list[tuple[str, int, bool, str | None]]:
    """Fetch function input parameters from pg_proc.

    Args:
        conn: Database connection
        function_name: Function name (e.g., 'api_list_agents_v3')
        schema: Schema name (default: 'public')
        function_oid: Optional function OID to disambiguate overloads

    Returns:
        List of (param_name, type_oid, has_default, default_expr) tuples
    """
    # Get function signature text to parse defaults
    # Note: pg_get_function_arguments can fail for some function signatures,
    # so we wrap it in a try/except and continue without defaults if it fails
    func_sig = None
    if function_oid:
        # When filtering by OID, query directly by OID
        try:
            func_sig = await conn.fetchrow(
                """
                SELECT pg_get_function_arguments($1) as arguments
                FROM pg_proc p
                WHERE p.oid = $1 AND p.prokind = 'f';
                """,
                function_oid,
            )
        except Exception:
            # pg_get_function_arguments can fail for complex signatures
            # We'll continue without default value parsing
            pass
    else:
        # When not filtering by OID, use schema and name
        try:
            func_sig = await conn.fetchrow(
                """
                SELECT pg_get_function_arguments(p.oid) as arguments
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = $1
                  AND p.proname = $2
                  AND p.prokind = 'f';
                """,
                schema,
                function_name,
            )
        except Exception:
            # pg_get_function_arguments can fail for complex signatures
            # We'll continue without default value parsing
            pass

    # Get basic parameter info
    # Note: proargtypes only includes input parameters, but proargnames may include output parameters
    # proargtypes is typically 0-indexed [0:N], proargnames is typically 1-indexed [1:M]
    # generate_subscripts returns indices starting from the array's lower bound
    if function_oid:
        # When filtering by OID, query directly by OID
        rows = await conn.fetch(
            """
            SELECT
              ord,
              CASE 
                WHEN p.proargnames IS NOT NULL 
                     AND (ord + array_lower(p.proargnames, 1) - array_lower(p.proargtypes, 1)) 
                         BETWEEN array_lower(p.proargnames, 1) AND array_upper(p.proargnames, 1)
                     AND ord BETWEEN array_lower(p.proargtypes, 1) AND array_upper(p.proargtypes, 1)
                THEN (p.proargnames)[ord + array_lower(p.proargnames, 1) - array_lower(p.proargtypes, 1)]
                ELSE format('arg_%s', ord - array_lower(p.proargtypes, 1) + 1)
              END as arg_name,
              (p.proargtypes)[ord] as arg_type_oid
            FROM pg_proc p
            CROSS JOIN generate_subscripts(p.proargtypes, 1) as ord
            WHERE p.oid = $1
              AND p.prokind = 'f'
            ORDER BY ord;
            """,
            function_oid,
        )
    else:
        # When not filtering by OID, use schema and name
        rows = await conn.fetch(
            """
            SELECT
              ord,
              CASE 
                WHEN p.proargnames IS NOT NULL 
                     AND (ord + array_lower(p.proargnames, 1) - array_lower(p.proargtypes, 1)) 
                         BETWEEN array_lower(p.proargnames, 1) AND array_upper(p.proargnames, 1)
                     AND ord BETWEEN array_lower(p.proargtypes, 1) AND array_upper(p.proargtypes, 1)
                THEN (p.proargnames)[ord + array_lower(p.proargnames, 1) - array_lower(p.proargtypes, 1)]
                ELSE format('arg_%s', ord - array_lower(p.proargtypes, 1) + 1)
              END as arg_name,
              (p.proargtypes)[ord] as arg_type_oid
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            CROSS JOIN generate_subscripts(p.proargtypes, 1) as ord
            WHERE n.nspname = $1
              AND p.proname = $2
              AND p.prokind = 'f'
            ORDER BY ord;
            """,
            schema,
            function_name,
        )

    # Parse defaults from function signature if available
    defaults_map: dict[int, tuple[bool, str | None]] = {}
    if func_sig and func_sig["arguments"]:
        import re

        args_text = func_sig["arguments"]
        # Pattern: param_name type DEFAULT value
        default_pattern = r"(\w+)\s+[^,\s]+\s+DEFAULT\s+([^,]+)"
        for match in re.finditer(default_pattern, args_text, re.IGNORECASE):
            param_name = match.group(1)
            default_value = match.group(2).strip()
            # Find which parameter index this is
            for i, row in enumerate(rows, start=1):
                if row["arg_name"] == param_name:
                    defaults_map[i] = (True, default_value)
                    break

    result = []
    for i, row in enumerate(rows, start=1):
        has_default, default_expr = defaults_map.get(i, (False, None))
        result.append((row["arg_name"], row["arg_type_oid"], has_default, default_expr))

    return result


async def fetch_function_return_columns(
    conn: asyncpg.Connection, function_name: str, schema: str = "public"
) -> list[tuple[str, int, bool]]:
    """Fetch return columns from a RETURNS TABLE function.

    For RETURNS TABLE functions, we parse the function definition
    to extract column names and types from the RETURNS TABLE clause.

    Args:
        conn: Database connection
        function_name: Function name (e.g., 'api_list_agents_v3')
        schema: Schema name (default: 'public')

    Returns:
        List of (col_name, type_oid, not_null) tuples
    """
    # Get function definition text
    func_def = await conn.fetchrow(
        """
        SELECT pg_get_functiondef(p.oid) as definition
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = $1
          AND p.proname = $2
          AND p.prokind = 'f';
        """,
        schema,
        function_name,
    )

    if not func_def or not func_def.get("definition"):
        return []

    definition = func_def["definition"]
    if not definition:
        return []

    # Parse RETURNS TABLE clause from definition
    # Pattern: RETURNS TABLE (col_name type, col_name type, ...)
    import re

    returns_table_match = re.search(
        r"RETURNS\s+TABLE\s*\(\s*(.*?)\s*\)", definition, re.IGNORECASE | re.DOTALL
    )

    if not returns_table_match:
        # Try calling function with proper type casts for NULL args
        func_info = await conn.fetchrow(
            """
            SELECT 
              p.proargtypes,
              p.proargnames
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = $1
              AND p.proname = $2
              AND p.prokind = 'f';
            """,
            schema,
            function_name,
        )

        if not func_info:
            return []

        # Build function call with properly typed NULL args
        num_params = len(func_info["proargtypes"]) if func_info["proargtypes"] else 0
        if num_params == 0:
            try:
                call_sql = f'SELECT * FROM "{schema}"."{function_name}"() LIMIT 0'
                stmt = await conn.prepare(call_sql)
                attrs = stmt.get_attributes()
                return [(attr.name, attr.type.oid, True) for attr in attrs]
            except Exception:
                return []
        else:
            # Can't safely call with NULL args - return empty
            return []

    # Parse column definitions from RETURNS TABLE clause
    columns_text = returns_table_match.group(1)
    if not columns_text:
        return []

    columns: list[tuple[str, int, bool]] = []

    # Split by commas, but be careful of commas inside type names
    # Pattern: col_name type [NOT NULL]
    # Handle array types like types.q_list_agents_v3_agent[]
    # Updated pattern to handle multiline and trailing commas better
    col_pattern = r"(\w+)\s+([^,\n]+?)(?:\s+NOT\s+NULL)?(?=\s*,|\s*$)"
    for match in re.finditer(col_pattern, columns_text, re.IGNORECASE):
        col_name = match.group(1)
        type_str = match.group(2)

        if not col_name or not type_str:
            continue

        type_str = type_str.strip()

        # Handle array types (e.g., types.q_list_agents_v3_agent[])
        is_array = type_str.endswith("[]")
        base_type_str = type_str[:-2] if is_array else type_str

        # Map PostgreSQL type aliases to actual type names
        type_name_mapping = {
            "boolean": "bool",
            "double precision": "float8",
            "character varying": "varchar",
            "character": "char",
            "bigint": "int8",
            "integer": "int4",
            "smallint": "int2",
            "timestamp with time zone": "timestamptz",
            "timestamp without time zone": "timestamp",
            "time with time zone": "timetz",
            "time without time zone": "time",
        }
        lookup_type = type_name_mapping.get(base_type_str.lower(), base_type_str)

        # Get type OID from type name
        # Try exact match first (for schema-qualified types like types.q_...)
        type_info = await conn.fetchrow(
            """
            SELECT t.oid, t.typarray
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE (n.nspname || '.' || t.typname) = $1
               OR t.typname = $1
            LIMIT 1;
            """,
            lookup_type,
        )

        if type_info:
            # If it's an array type, use the array OID (typarray points to the array type)
            if is_array and type_info["typarray"]:
                type_oid = type_info["typarray"]  # This is the array type OID
            else:
                type_oid = type_info["oid"]
            # Check if NOT NULL is in the column definition
            not_null = "NOT NULL" in columns_text[match.start() : match.end()].upper()
            columns.append((col_name, type_oid, not_null))
        else:
            # Type lookup failed - log for debugging but don't fail completely
            # This can happen for custom types that aren't in pg_type yet
            # We'll skip this column but continue processing others
            pass

    return columns


def _is_function_sql(sql_text: str) -> tuple[bool, str | None, str | None]:
    """Detect if SQL contains a CREATE OR REPLACE FUNCTION.

    Args:
        sql_text: SQL query text

    Returns:
        Tuple of (is_function, function_name, schema_name)
    """
    import re

    # Pattern: CREATE OR REPLACE FUNCTION [schema.]function_name
    pattern = r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+(?:(\w+)\.)?(\w+)\s*\("
    match = re.search(pattern, sql_text, re.IGNORECASE)

    if match:
        schema = match.group(1) or "public"
        func_name = match.group(2)
        return True, func_name, schema

    return False, None, None


async def _find_function_oid_by_signature(
    conn: asyncpg.Connection, function_name: str, schema: str, sql_text: str
) -> int | None:
    """Find function OID by matching SQL signature to database function signatures.

    Extracts the function signature from SQL file and matches it to the correct overload.

    Args:
        conn: Database connection
        function_name: Function name
        schema: Schema name
        sql_text: SQL file content

    Returns:
        Function OID if found, None otherwise
    """
    import re

    # Extract function signature from SQL: FUNCTION name(param1 type1, param2 type2, ...)
    # Pattern matches the parameter list between parentheses
    pattern = rf"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+(?:{re.escape(schema)}\.)?{re.escape(function_name)}\s*\((.*?)\)"
    match = re.search(pattern, sql_text, re.IGNORECASE | re.DOTALL)

    if not match:
        return None

    # Get all overloads
    overloads = await conn.fetch(
        """
        SELECT p.oid, pg_get_function_identity_arguments(p.oid) as sig
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = $1
          AND p.proname = $2
          AND p.prokind = 'f';
        """,
        schema,
        function_name,
    )

    if len(overloads) <= 1:
        # No overloads or single function - return first OID
        if overloads:
            oid_val = overloads[0]["oid"]
            return int(oid_val) if oid_val is not None else None
        return None

    # Normalize SQL signature: remove whitespace, convert to lowercase
    sql_params = match.group(1).strip()
    sql_params_normalized = re.sub(r"\s+", " ", sql_params).lower()

    # Try to match against database signatures
    for overload in overloads:
        db_sig_normalized = re.sub(r"\s+", " ", overload["sig"]).lower()
        # Compare normalized signatures
        if sql_params_normalized == db_sig_normalized:
            oid_val = overload["oid"]
            return int(oid_val) if oid_val is not None else None

    # If no exact match, return the most recent OID (highest OID typically means newest)
    # This is a fallback - exact matching is preferred
    oids: list[int] = []
    for overload in overloads:
        oid_val = overload["oid"]
        if oid_val is not None:
            oids.append(int(oid_val))
    if oids:
        return max(oids)
    return None


async def introspect_function(
    sql_path: str, conn: asyncpg.Connection, function_name: str, schema: str = "public"
) -> SQLMetadata:
    """Introspect a PostgreSQL function to extract parameter and return types.

    Args:
        sql_path: Path to SQL file (for metadata)
        conn: Database connection
        function_name: Function name (e.g., 'api_list_agents_v3')
        schema: Schema name (default: 'public')

    Returns:
        SQLMetadata with parameter and return column information
    """
    try:
        # Check if function exists first
        func_exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE p.proname = $1
                AND n.nspname = $2
                AND p.prokind = 'f'
            )
            """,
            function_name,
            schema,
        )

        # Check for multiple overloads
        overloads = await conn.fetch(
            """
            SELECT p.oid, pg_get_function_identity_arguments(p.oid) as sig
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = $1
              AND p.proname = $2
              AND p.prokind = 'f';
            """,
            schema,
            function_name,
        )

        if not func_exists:
            return SQLMetadata(
                sql_path=sql_path,
                parameters=[],
                returns=[],
                error=f"Function {schema}.{function_name} does not exist in database",
            )

        # If multiple overloads exist, find the correct one by matching SQL signature
        function_oid = None
        if len(overloads) > 1:
            sql_text = load_sql(sql_path)
            function_oid = await _find_function_oid_by_signature(
                conn, function_name, schema, sql_text
            )

        # Get input parameters (filtered by OID if multiple overloads)
        input_params = await fetch_function_inputs(
            conn, function_name, schema, function_oid
        )

        param_types: list[ColumnMetadata] = []
        for param_name, type_oid, has_default, default_expr in input_params:
            # Get full type information including typelem and typcategory for reliable array detection
            type_info = await conn.fetchrow(
                """
                SELECT 
                  t.typtype,
                  t.typarray,
                  t.typelem,
                  t.typcategory,
                  (n.nspname || '.' || t.typname) as full_name
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.oid = $1
                """,
                type_oid,
            )

            if type_info:
                typtype = type_info["typtype"]
                full_name = type_info["full_name"]
                typelem = type_info["typelem"]
                typcategory = type_info["typcategory"]

                # Definitive array check using typcategory
                # PostgreSQL sets typcategory='A' for all array types
                if typcategory == "A" or typcategory == b"A":
                    # This is an array type - get the element type
                    elem_oid = int(typelem) if typelem else 0

                    if elem_oid:
                        elem_info = await conn.fetchrow(
                            """
                            SELECT
                              t.typtype,
                              t.typbasetype,
                              (n.nspname || '.' || t.typname) AS full_name
                            FROM pg_type t
                            JOIN pg_namespace n ON n.oid = t.typnamespace
                            WHERE t.oid = $1
                            """,
                            elem_oid,
                        )

                        if elem_info and (
                            elem_info["typtype"] == "c" or elem_info["typtype"] == b"c"
                        ):
                            # Composite array - element type is composite
                            python_type = f"CompositeArray({elem_info['full_name']})"
                            is_array = True
                        elif elem_info and (
                            elem_info["typtype"] == "d" or elem_info["typtype"] == b"d"
                        ):
                            # Domain type - unwrap to base type
                            base_oid = elem_info["typbasetype"]
                            if base_oid:
                                base_info = await conn.fetchrow(
                                    """
                                    SELECT
                                      t.typtype,
                                      (n.nspname || '.' || t.typname) AS full_name
                                    FROM pg_type t
                                    JOIN pg_namespace n ON n.oid = t.typnamespace
                                    WHERE t.oid = $1
                                    """,
                                    base_oid,
                                )
                                if base_info and (
                                    base_info["typtype"] == "c"
                                    or base_info["typtype"] == b"c"
                                ):
                                    python_type = (
                                        f"CompositeArray({base_info['full_name']})"
                                    )
                                    is_array = True
                                else:
                                    python_type, is_array = await _oid_to_python_type(
                                        type_oid, conn
                                    )
                            else:
                                python_type, is_array = await _oid_to_python_type(
                                    type_oid, conn
                                )
                        else:
                            # Normal array (text[], uuid[], etc.)
                            python_type, is_array = await _oid_to_python_type(
                                type_oid, conn
                            )
                    else:
                        # Array type but no element type (shouldn't happen, but fallback)
                        python_type, is_array = await _oid_to_python_type(
                            type_oid, conn
                        )
                elif typtype == "c" or typtype == b"c":
                    # Composite type (not array)
                    python_type = f"Composite({full_name})"
                    is_array = False
                else:
                    # Regular type, not composite
                    python_type, is_array = await _oid_to_python_type(type_oid, conn)
            else:
                # Fallback to standard type resolution
                python_type, is_array = await _oid_to_python_type(type_oid, conn)

            param_types.append(
                ColumnMetadata(
                    name=param_name,
                    python_type=python_type,
                    pg_oid=type_oid,
                    is_array=is_array,
                    is_optional=has_default,
                    default_value=default_expr,
                )
            )

        # Get return columns - try calling function with NULL args
        # But first, let's try to get from information_schema
        return_cols = await fetch_function_return_columns(conn, function_name, schema)

        return_types: list[ColumnMetadata] = []
        for col_name, type_oid, not_null in return_cols:
            if type_oid == 0:
                # Try to get from information_schema
                continue

            # Check if it's an array first
            type_info = await conn.fetchrow(
                """
                SELECT 
                  typtype,
                  typarray,
                  (n.nspname || '.' || t.typname) as full_name
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.oid = $1
                """,
                type_oid,
            )

            if type_info:
                typtype = type_info["typtype"]
                typarray = type_info["typarray"]
                full_name = type_info["full_name"]

                # Check if it's a composite type array
                # PostgreSQL array types: if typarray != 0, this type IS the array type, and typarray points to the base type
                # If typarray == 0, this might still be an array type (name starts with '_') - find base type by looking for type with typarray = this oid
                if typarray != 0:
                    # This type IS an array type - typarray points to the base type
                    # Check if the base type (pointed to by typarray) is composite
                    base_info = await conn.fetchrow(
                        """
                        SELECT 
                          t.typtype, 
                          (n.nspname || '.' || t.typname) as full_name
                        FROM pg_type t
                        JOIN pg_namespace n ON n.oid = t.typnamespace
                        WHERE t.oid = $1
                        """,
                        typarray,
                    )
                    if base_info and (
                        base_info["typtype"] == "c" or base_info["typtype"] == b"c"
                    ):
                        # Composite array - base type is composite
                        python_type = f"CompositeArray({base_info['full_name']})"
                        is_array = True
                    else:
                        # Regular array, not composite
                        python_type, is_array = await _oid_to_python_type(
                            type_oid, conn
                        )
                elif (typtype == "b" or typtype == b"b") and full_name.startswith(
                    "types._"
                ):
                    # This is an array type (name starts with '_') - find the base type
                    base_info = await conn.fetchrow(
                        """
                        SELECT 
                          t.typtype, 
                          (n.nspname || '.' || t.typname) as full_name
                        FROM pg_type t
                        JOIN pg_namespace n ON n.oid = t.typnamespace
                        WHERE t.typarray = $1
                        """,
                        type_oid,
                    )
                    if base_info and (
                        base_info["typtype"] == "c" or base_info["typtype"] == b"c"
                    ):
                        # Composite array - base type is composite
                        python_type = f"CompositeArray({base_info['full_name']})"
                        is_array = True
                    else:
                        # Regular array, not composite
                        python_type, is_array = await _oid_to_python_type(
                            type_oid, conn
                        )
                elif typtype == "c" or typtype == b"c":
                    # Composite type (not array)
                    python_type = f"Composite({full_name})"
                    is_array = False
                elif typtype == "c" or typtype == b"c":
                    # Composite type (not array)
                    python_type = f"Composite({full_name})"
                    is_array = False
                else:
                    python_type, is_array = await _oid_to_python_type(type_oid, conn)
            else:
                python_type, is_array = await _oid_to_python_type(type_oid, conn)

            return_types.append(
                ColumnMetadata(
                    name=col_name,
                    python_type=python_type,
                    pg_oid=type_oid,
                    is_array=is_array,
                    is_optional=not not_null,
                )
            )

        # If we couldn't get return columns from information_schema,
        # try calling the function with NULL args (if it has defaults or is safe)
        if not return_types:
            # Try to call function to get structure
            # This is risky, so we'll handle it carefully
            try:
                # Build call with NULL args
                null_args = ", ".join(["NULL"] * len(input_params))
                call_sql = (
                    f"SELECT * FROM {schema}.{function_name}({null_args}) LIMIT 0"
                )
                stmt = await conn.prepare(call_sql)
                attrs = stmt.get_attributes()

                for attr in attrs:
                    python_type, is_array = await _oid_to_python_type(
                        attr.type.oid, conn
                    )
                    return_types.append(
                        ColumnMetadata(
                            name=attr.name,
                            python_type=python_type,
                            pg_oid=attr.type.oid,
                            is_array=is_array,
                            is_optional=False,
                        )
                    )
            except Exception:
                # Can't call function - that's okay, we'll handle it in type generation
                pass

        result = SQLMetadata(
            sql_path=sql_path,
            parameters=param_types,
            returns=return_types,
        )

        return result

    except Exception as e:
        return SQLMetadata(
            sql_path=sql_path,
            parameters=[],
            returns=[],
            error=f"Failed to introspect function: {str(e)}",
        )


async def _oid_to_python_type(oid: int, conn: asyncpg.Connection) -> tuple[str, bool]:
    """Map Postgres OID to Python type string.

    Args:
        oid: Postgres type OID
        conn: Database connection for querying type info

    Returns:
        Tuple of (python_type_string, is_array)
    """
    # Check if it's a known type (array or base)
    if oid in OID_TO_PYTHON_TYPE:
        # Check if it's an array type by OID range
        # Array OIDs are typically > 1000 for common types
        is_array = oid >= 1000 and oid < 2000
        return OID_TO_PYTHON_TYPE[oid], is_array

    # Query pg_type to get type information
    try:
        type_info = await conn.fetchrow(
            """
            SELECT 
                t.typname,
                t.typarray,
                t.typtype,
                (n.nspname || '.' || t.typname) as full_name
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE t.oid = $1
            """,
            oid,
        )
        if type_info:
            typname = type_info["typname"]
            typarray = type_info["typarray"]
            typtype = type_info["typtype"]
            full_name = type_info["full_name"]

            # Handle enum types (typtype='e' or b'e')
            # Postgres enums are represented as strings in Python/asyncpg
            if typtype == "e" or typtype == b"e":  # enum type
                return "str", False

            # Handle composite types (typtype='c' or b'c')
            # Composite types need special handling - we'll generate models for them
            if typtype == "c" or typtype == b"c":  # composite type
                # Return a special marker that includes the full type name with schema
                return f"Composite({full_name})", False

            # If this type has an array type (typarray != 0), it's a base type
            # If typarray is 0 and typname ends with [], it's an array type
            if typname and typname.endswith("[]"):
                # Extract base type name
                base_name = typname[:-2]
                # Map common base types to array types
                if base_name in ("text", "varchar", "char", "name", "bpchar"):
                    return "list[str]", True
                if base_name in ("int4", "integer", "int"):
                    return "list[int]", True
                if base_name in ("int8", "bigint"):
                    return "list[int]", True
                if base_name in ("int2", "smallint"):
                    return "list[int]", True
                if base_name in ("bool", "boolean"):
                    return "list[bool]", True
                if base_name == "uuid":
                    return "list[UUID]", True
                if base_name in ("timestamp", "timestamptz"):
                    return "list[datetime]", True
                if base_name == "date":
                    return "list[date]", True
                if base_name in ("time", "timetz"):
                    return "list[time]", True
                if base_name in ("json", "jsonb"):
                    return "list[dict[str, Any]]", True
                if base_name in ("float4", "real"):
                    return "list[float]", True
                if base_name in ("float8", "double precision"):
                    return "list[float]", True
                if base_name == "numeric":
                    return "list[float]", True
            else:
                # Base type - map common types
                if typname in ("text", "varchar", "char", "name", "bpchar"):
                    return "str", False
                if typname in ("int4", "integer", "int"):
                    return "int", False
                if typname in ("int8", "bigint"):
                    return "int", False
                if typname in ("int2", "smallint"):
                    return "int", False
                if typname in ("bool", "boolean"):
                    return "bool", False
                if typname == "uuid":
                    return "UUID", False
                if typname in ("timestamp", "timestamptz"):
                    return "datetime", False
                if typname == "date":
                    return "date", False
                if typname in ("time", "timetz"):
                    return "time", False
                if typname in ("json", "jsonb"):
                    return "dict[str, Any]", False
                if typname in ("float4", "real"):
                    return "float", False
                if typname in ("float8", "double precision"):
                    return "float", False
                if typname == "numeric":
                    return "float", False
    except Exception:
        pass

    # Fallback to Any for unknown types
    return "Any", False


async def introspect_sql_file(sql_path: str, conn: asyncpg.Connection) -> SQLMetadata:
    """Introspect a SQL file to extract parameter and return types.

    Args:
        sql_path: Path to SQL file (relative to server root, e.g., "app/sql/v3/agents/create_agent_complete.sql")
        conn: Database connection for PREPARE and introspection

    Returns:
        SQLMetadata with parameter and return column information
    """
    try:
        # Load SQL file
        sql_text = load_sql(sql_path)

        # Check if this is a function definition
        is_function, function_name, schema = _is_function_sql(sql_text)
        if is_function and function_name:
            # Introspect as function (use 'public' as default schema if None)
            schema_name = schema or "public"
            result = await introspect_function(
                sql_path, conn, function_name, schema_name
            )
            return result

        # Use a unique name to avoid conflicts
        stmt_name = f"introspect_{abs(hash(sql_path)) % 1000000}"

        try:
            # Use asyncpg's prepare() directly - it handles SQL escaping properly
            # This gives us return types reliably
            stmt = await conn.prepare(sql_text)

            # Get return column types
            return_types: list[ColumnMetadata] = []
            attrs = stmt.get_attributes()
            column_names = [attr.name for attr in attrs]

            # Detect nullable columns from SQL patterns
            nullable_columns = _detect_nullable_columns(sql_text, column_names)

            for attr in attrs:
                python_type, is_array = await _oid_to_python_type(attr.type.oid, conn)
                is_optional = attr.name in nullable_columns
                return_types.append(
                    ColumnMetadata(
                        name=attr.name,
                        python_type=python_type,
                        pg_oid=attr.type.oid,
                        is_array=is_array,
                        is_optional=is_optional,
                    )
                )

            # Get parameter types from asyncpg's prepared statement
            # asyncpg's prepare() exposes parameter types via get_parameters()
            param_types: list[ColumnMetadata] = []
            try:
                # Parse @params block (primary source of truth for names, optionality, defaults)
                atparams_metadata = _parse_atparams_block(sql_text)

                # Fallback: extract parameter names from params CTE or comments
                param_names = _extract_param_names_from_params_cte(sql_text)

                param_type_objs = stmt.get_parameters()
                if param_type_objs:
                    for i, param_type_obj in enumerate(param_type_objs, start=1):
                        python_type, is_array = await _oid_to_python_type(
                            param_type_obj.oid, conn
                        )

                        # Get metadata from @params block if available
                        if i in atparams_metadata:
                            meta = atparams_metadata[i]
                            param_name = meta["name"]
                            is_optional = meta["optional"]
                            default_value = meta["default"]
                        else:
                            # Fallback to CTE/comment parsing
                            param_name = param_names.get(i, f"${i}")
                            is_optional = False
                            default_value = None

                        param_types.append(
                            ColumnMetadata(
                                name=param_name,
                                python_type=python_type,
                                pg_oid=param_type_obj.oid,
                                is_array=is_array,
                                is_optional=is_optional,
                                default_value=default_value,
                            )
                        )
            except Exception:
                # If we can't get parameter types, that's okay - we still have return types
                # Parameter types can be inferred from SQL comments or left as empty
                pass

            return SQLMetadata(
                sql_path=sql_path,
                parameters=param_types,
                returns=return_types,
            )

        except Exception as e:
            # Try to clean up on error
            try:
                await conn.execute(f"DEALLOCATE {stmt_name}")
            except Exception:
                pass
            return SQLMetadata(
                sql_path=sql_path,
                parameters=[],
                returns=[],
                error=f"Failed to prepare SQL: {str(e)}",
            )

    except FileNotFoundError:
        return SQLMetadata(
            sql_path=sql_path,
            parameters=[],
            returns=[],
            error=f"SQL file not found: {sql_path}",
        )
    except Exception as e:
        return SQLMetadata(
            sql_path=sql_path,
            parameters=[],
            returns=[],
            error=f"Error loading SQL file: {str(e)}",
        )
