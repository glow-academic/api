#!/usr/bin/env python3
"""Apply boolean filter pattern to all resource SEARCH endpoints.

This script transforms SQL and Python files to replace the broken suggest_source='linked'
pattern with explicit boolean parameters for each artifact junction table.

Usage:
    python scripts/apply_boolean_filters.py
"""

import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(BASE_DIR, "server/app/sql/v4/queries/resources")
PY_DIR = os.path.join(BASE_DIR, "server/app/api/v4/resources")

# ============================================================================
# RESOURCE CONFIGURATION
# ============================================================================
# Each resource maps to its artifact booleans.
# Format: {resource_name: [list of artifact booleans]}
# Junction table = {artifact}_{resource}_junction (with exceptions below)
# FK column = singular form of resource + _id (with exceptions below)

RESOURCE_BOOLEANS = {
    # 17 booleans
    "departments": [
        "agent",
        "auth",
        "cohort",
        "department",
        "document",
        "eval",
        "field",
        "model",
        "parameter",
        "persona",
        "profile",
        "provider",
        "rubric",
        "scenario",
        "setting",
        "simulation",
        "tool",
    ],
    "flags": [
        "agent",
        "auth",
        "cohort",
        "department",
        "document",
        "eval",
        "field",
        "model",
        "parameter",
        "persona",
        "profile",
        "provider",
        "rubric",
        "scenario",
        "setting",
        "simulation",
        "tool",
    ],
    # 16 booleans (all except profile)
    "descriptions": [
        "agent",
        "auth",
        "cohort",
        "department",
        "document",
        "eval",
        "field",
        "model",
        "parameter",
        "persona",
        "provider",
        "rubric",
        "scenario",
        "setting",
        "simulation",
        "tool",
    ],
    # 4 booleans
    "parameters": ["document", "parameter", "persona", "scenario"],
    # 3 booleans
    "parameter_fields": ["document", "persona", "scenario"],
    # 2 booleans
    "instructions": ["agent", "persona"],
    "colors": ["persona", "setting"],
    "models": ["agent", "model"],
    "voices": ["agent", "model"],
    "temperature_levels": ["agent", "model"],
    "reasoning_levels": ["agent", "model"],
    "values": ["model", "provider"],
    "providers": ["model", "provider"],
    "documents": ["document", "scenario"],
    "personas": ["persona", "scenario"],
    "scenarios": ["scenario", "simulation"],
    "simulations": ["cohort", "simulation"],
    "agents": ["agent", "setting"],
    "auths": ["auth", "setting"],
    "cohorts": ["cohort", "profile"],
    "profiles": ["profile", "setting"],
    "roles": ["profile", "setting"],
    "settings": ["department", "setting"],
    "tools": ["agent", "tool"],
    "fields": ["field", "parameter"],
    # 1 boolean
    "icons": ["persona"],
    "examples": ["persona"],
    "prompts": ["agent"],
    "arg_positions": ["tool"],
    "args": ["tool"],
    "args_outputs": ["tool"],
    "bindings": ["tool"],
    "domains": ["tool"],
    "items": ["auth"],
    "protocols": ["auth"],
    "slugs": ["auth"],
    "emails": ["profile"],
    "routes": ["profile"],
    "request_limits": ["profile"],
    "endpoints": ["provider"],
    "keys": ["provider"],
    "modalities": ["model"],
    "pricing": ["model"],
    "qualities": ["model"],
    "conditional_parameters": ["field"],
    "evals": ["eval"],
    "groups": ["eval"],
    "runs": ["eval"],
    "group_positions": ["eval"],
    "group_rubrics": ["eval"],
    "run_positions": ["eval"],
    "run_rubrics": ["eval"],
    "rubrics": ["rubric"],
    "points": ["rubric"],
    "standard_groups": ["rubric"],
    "standards": ["rubric"],
    "uploads": ["document"],
    "images": ["scenario"],
    "objectives": ["scenario"],
    "options": ["scenario"],
    "problem_statements": ["scenario"],
    "questions": ["scenario"],
    "videos": ["scenario"],
    "scenario_flags": ["simulation"],
    "scenario_personas": ["simulation"],
    "scenario_positions": ["simulation"],
    "scenario_rubrics": ["simulation"],
    "scenario_time_limits": ["simulation"],
    "simulation_positions": ["cohort"],
    "auth_item_keys": ["setting"],
    "provider_keys": ["setting"],
    "role_routes": ["setting"],
    "thresholds": ["setting"],
    # 0 booleans - skip
    # "texts": [],
}

# Junction table name overrides (default: {artifact}_{resource}_junction)
JUNCTION_OVERRIDES = {
    ("eval", "group_rubrics"): "eval_groups_rubrics_junction",
    ("eval", "run_rubrics"): "eval_runs_rubrics_junction",
}

# FK column name overrides (default: singular(resource) + _id)
FK_OVERRIDES = {
    "args": "args_id",
    "arg_positions": "arg_positions_id",
    "role_routes": "role_routes_id",
    "group_positions": "group_positions_id",
    "group_rubrics": "group_rubric_id",
    "run_rubrics": "run_rubric_id",
}

# Resources that should be SKIPPED entirely (already done or no changes needed)
SKIP_RESOURCES = {"names", "texts"}


def singular(resource_name):
    """Convert plural resource name to singular FK column name."""
    if resource_name in FK_OVERRIDES:
        return FK_OVERRIDES[resource_name]

    name = resource_name
    # Handle compound names: convert each part
    if "_" in name:
        parts = name.split("_")
        # Singularize the last part only
        last = parts[-1]
        if last.endswith("ies"):
            last = last[:-3] + "y"
        elif last.endswith("ses"):
            last = last[:-2]
        elif last.endswith("s") and not last.endswith("ss"):
            last = last[:-1]
        parts[-1] = last
        return "_".join(parts) + "_id"
    else:
        if name.endswith("ies"):
            name = name[:-3] + "y"
        elif name.endswith("ses"):
            name = name[:-2]
        elif name.endswith("s") and not name.endswith("ss"):
            name = name[:-1]
        return name + "_id"


def junction_table(artifact, resource):
    """Get junction table name for artifact-resource pair."""
    key = (artifact, resource)
    if key in JUNCTION_OVERRIDES:
        return JUNCTION_OVERRIDES[key]
    return f"{artifact}_{resource}_junction"


def camel_case(snake_str):
    """Convert snake_case to CamelCase."""
    return "".join(word.capitalize() for word in snake_str.split("_"))


# ============================================================================
# SQL TRANSFORMATION
# ============================================================================


def transform_sql(resource, booleans):
    """Transform a resource's search SQL file to add boolean filters."""
    sql_file = os.path.join(SQL_DIR, resource, f"search_{resource}_complete.sql")
    if not os.path.exists(sql_file):
        print(f"  WARNING: SQL file not found: {sql_file}")
        return False

    with open(sql_file) as f:
        content = f.read()

    # Skip if already transformed (has boolean params)
    if f"    {booleans[0]} boolean DEFAULT false" in content:
        print("  SQL already transformed, skipping")
        return True

    # 1. Find the closing paren of the function signature and add boolean params
    # Pattern: find the last param line before the closing )
    # We need to add booleans after the last existing param

    # Find the function signature block
    func_sig_pattern = r"(CREATE OR REPLACE FUNCTION api_search_\w+_v4\(.*?\))"
    func_sig_match = re.search(func_sig_pattern, content, re.DOTALL)
    if not func_sig_match:
        print(f"  WARNING: Could not find function signature in {sql_file}")
        return False

    func_sig = func_sig_match.group(1)

    # Find the last param before the closing )
    # Split the signature into lines
    sig_lines = func_sig.split("\n")

    # Find the line with the closing paren
    close_paren_idx = None
    for i in range(len(sig_lines) - 1, -1, -1):
        if sig_lines[i].strip() == ")":
            close_paren_idx = i
            break

    if close_paren_idx is None:
        print("  WARNING: Could not find closing paren in signature")
        return False

    # Add boolean params before the closing paren
    # First, ensure the last param line ends with a comma
    last_param_idx = close_paren_idx - 1
    if not sig_lines[last_param_idx].rstrip().endswith(","):
        sig_lines[last_param_idx] = sig_lines[last_param_idx].rstrip() + ","

    # Build boolean param lines
    bool_comment = "    -- Artifact boolean filters: when true, only return resources linked to that artifact type"
    bool_lines = [bool_comment]
    for i, b in enumerate(booleans):
        comma = "," if i < len(booleans) - 1 else ""
        bool_lines.append(f"    {b} boolean DEFAULT false{comma}")

    # Insert boolean lines before closing paren
    new_sig_lines = (
        sig_lines[:close_paren_idx] + bool_lines + sig_lines[close_paren_idx:]
    )
    new_func_sig = "\n".join(new_sig_lines)

    content = content.replace(func_sig, new_func_sig)

    # 2. Remove the suggest_source='linked' block if present
    # Pattern: the linked block within the suggest_source filter
    linked_patterns = [
        # Pattern 1: with leading OR
        r"\s+OR \(\s+suggest_source = 'linked'\s+AND EXISTS \(\s+SELECT 1 FROM \w+ \w+\s+WHERE \w+\.\w+ = \w+\.id\s+AND \w+\.active = true\s+\)\s+\)",
        # Pattern 2: alternative formatting
        r"\s+OR \(\s+suggest_source = 'linked'\s+AND EXISTS \(\s+SELECT 1\s+FROM \w+ \w+\s+WHERE \w+\.\w+ = \w+\.id\s+AND \w+\.active = true\s+\)\s+\)",
    ]

    for pattern in linked_patterns:
        content = re.sub(pattern, "", content)

    # 3. Find the table alias from the FROM clause
    alias_match = re.search(rf"FROM {resource}_resource (\w+)", content)
    if not alias_match:
        print(f"  WARNING: Could not find table alias for {resource}")
        return False
    alias = alias_match.group(1)

    # 4. Add EXISTS filters before the ORDER BY clause
    # Find the ORDER BY line inside the subquery
    fk_col = singular(resource)

    # Build EXISTS filter lines
    exists_lines = []
    exists_lines.append(
        "      -- Artifact boolean filters (each filters to resources linked to at least one of that artifact type)"
    )
    func_name = f"api_search_{resource}_v4"
    for b in booleans:
        jt = junction_table(b, resource)
        exists_lines.append(
            f"      AND (NOT {b} OR EXISTS (SELECT 1 FROM {jt} j WHERE j.{fk_col} = {alias}.id AND j.active = true))"
        )

    exists_block = "\n".join(exists_lines)

    # Insert before ORDER BY in the subquery
    # Find the ORDER BY that's inside the subquery (indented)
    order_match = re.search(r"(\n    ORDER BY)", content)
    if order_match:
        insert_pos = order_match.start()
        content = content[:insert_pos] + "\n" + exists_block + content[insert_pos:]
    else:
        print(f"  WARNING: Could not find ORDER BY in {sql_file}")
        return False

    # 5. Update the comment at the top
    old_comment_match = re.search(r"^-- Search.*?\n(-- .*?\n)*", content)

    with open(sql_file, "w") as f:
        f.write(content)

    print(f"  SQL transformed: {len(booleans)} booleans added")
    return True


# ============================================================================
# PYTHON TRANSFORMATION
# ============================================================================


def transform_python(resource, booleans):
    """Transform a resource's search.py file to add boolean filters."""
    py_file = os.path.join(PY_DIR, resource, "search.py")
    if not os.path.exists(py_file):
        print(f"  WARNING: Python file not found: {py_file}")
        return False

    with open(py_file) as f:
        content = f.read()

    # Skip if already transformed
    if f"    {booleans[0]}: bool = False" in content:
        print("  Python already transformed, skipping")
        return True

    class_name = camel_case(resource)
    resource_upper = camel_case(resource)

    # Determine if this file uses auto-generated SqlParams
    sql_params_class = f"Search{resource_upper}SqlParams"
    has_sql_params = sql_params_class in content

    # Determine existing params from the internal function signature
    internal_func_match = re.search(
        rf"async def search_{resource}_internal\((.*?)\) -> ",
        content,
        re.DOTALL,
    )
    if not internal_func_match:
        print(f"  WARNING: Could not find internal function in {py_file}")
        return False

    func_params_str = internal_func_match.group(1)

    # Parse the params to understand the function signature
    # Check for various param patterns
    has_draft_id = "draft_id" in func_params_str
    has_suggest_source = "suggest_source" in func_params_str
    has_exclude_ids = "exclude_ids" in func_params_str
    has_user_department_ids = "user_department_ids" in func_params_str
    has_artifact_type = "artifact_type" in func_params_str

    # Special case: some resources have custom params (parameter_ids, scenario_ids, args_ids)
    is_id_list_pattern = False
    id_list_param = None
    for param_name in ["parameter_ids", "scenario_ids", "args_ids"]:
        if param_name in func_params_str:
            is_id_list_pattern = True
            id_list_param = param_name
            break

    # 1. Add imports if needed
    if "from pydantic import BaseModel" not in content:
        # Add BaseModel import
        content = content.replace(
            "from fastapi import APIRouter, Depends, HTTPException, Request, Response",
            "from fastapi import APIRouter, Depends, HTTPException, Request, Response\nfrom pydantic import BaseModel",
        )

    if (
        "from typing import Annotated, cast" in content
        and "Any" not in content.split("from typing import")[1].split("\n")[0]
    ):
        content = content.replace(
            "from typing import Annotated, cast",
            "from typing import Annotated, Any, cast",
        )
    elif "from typing import cast" in content and "Any" not in content:
        content = content.replace(
            "from typing import cast",
            "from typing import Any, cast",
        )

    # 2. Remove SqlParams from imports if present (we'll use handcrafted)
    if has_sql_params:
        content = content.replace(f"    {sql_params_class},\n", "")

    # 3. Build the handcrafted Params class
    params_class_name = f"Search{resource_upper}Params"

    params_fields = []
    params_tuple_fields = []

    if is_id_list_pattern:
        # ID-list pattern: different structure
        params_fields.append(f"    {id_list_param}: list[UUID] = []")
        params_tuple_fields.append(f"            self.{id_list_param},")
        if "limit_count" in func_params_str:
            params_fields.append("    limit_count: int | None = 100")
            params_tuple_fields.append("            self.limit_count,")
        if "offset_count" in func_params_str:
            params_fields.append("    offset_count: int | None = 0")
            params_tuple_fields.append("            self.offset_count,")
    else:
        params_fields.append("    search: str | None = None")
        params_tuple_fields.append("            self.search,")
        params_fields.append("    limit_count: int | None = 20")
        params_tuple_fields.append("            self.limit_count,")
        params_fields.append("    offset_count: int | None = 0")
        params_tuple_fields.append("            self.offset_count,")

        if has_user_department_ids:
            params_fields.append("    user_department_ids: list[UUID] = []")
            params_tuple_fields.append("            self.user_department_ids,")

        if has_draft_id:
            params_fields.append("    draft_id: UUID | None = None")
            params_tuple_fields.append("            self.draft_id,")

        if has_suggest_source:
            params_fields.append('    suggest_source: str | None = "all"')
            params_tuple_fields.append("            self.suggest_source,")

        if has_exclude_ids:
            params_fields.append("    exclude_ids: list[UUID] = []")
            params_tuple_fields.append("            self.exclude_ids,")

    # Add boolean fields
    params_fields.append("    # Artifact boolean filters")
    for b in booleans:
        params_fields.append(f"    {b}: bool = False")
        params_tuple_fields.append(f"            self.{b},")

    params_class = f"""
# Handcrafted params to match SQL signature with artifact boolean filters
class {params_class_name}(BaseModel):
{chr(10).join(params_fields)}

    def to_tuple(self) -> tuple[Any, ...]:
        return (
{chr(10).join(params_tuple_fields)}
        )

"""

    # 4. Insert the params class before the internal function
    # Find the right insertion point
    insert_marker = f"async def search_{resource}_internal("
    insert_idx = content.find(insert_marker)
    if insert_idx == -1:
        print("  WARNING: Could not find insertion point")
        return False

    # Find the start of the line (may have preceding newlines)
    line_start = content.rfind("\n", 0, insert_idx) + 1
    content = content[:line_start] + params_class + content[line_start:]

    # Re-find the internal function after insertion
    insert_marker = f"async def search_{resource}_internal("
    func_start = content.find(insert_marker)

    # 5. Add boolean kwargs to internal function signature
    # Find the closing of the function signature
    func_sig_start = func_start
    func_sig_end = content.find("):", func_sig_start)
    if func_sig_end == -1:
        # Try with ) -> pattern
        func_sig_end = content.find(") ->", func_sig_start)
    if func_sig_end == -1:
        print("  WARNING: Could not find end of internal function signature")
        return False

    current_sig = content[func_sig_start:func_sig_end]

    # Check if bypass_cache is present
    has_bypass = "bypass_cache" in current_sig

    # Remove artifact_type param if present (for flags)
    if has_artifact_type:
        current_sig = re.sub(
            r",?\s*\n\s*artifact_type:\s*str\s*\|\s*None\s*=\s*None,?", "", current_sig
        )
        # Also remove from the section after the function signature
        # We'll handle this below

    # Add keyword-only boolean params after bypass_cache (or after last param)
    bool_kwargs = []
    bool_kwargs.append("    *,")
    for b in booleans:
        bool_kwargs.append(f"    {b}: bool = False,")

    # Find where to insert the boolean kwargs
    if has_bypass:
        # Insert after bypass_cache line
        bypass_pattern = r"(    bypass_cache: bool = False,?)"
        bypass_match = re.search(bypass_pattern, current_sig)
        if bypass_match:
            insert_after = bypass_match.end()
            # Make sure bypass_cache line ends with comma
            if not bypass_match.group(1).endswith(","):
                current_sig = (
                    current_sig[: bypass_match.end()]
                    + ","
                    + current_sig[bypass_match.end() :]
                )
                insert_after += 1
            bool_block = "\n" + "\n".join(bool_kwargs)
            new_sig = (
                current_sig[:insert_after]
                + bool_block
                + "\n"
                + current_sig[insert_after:]
            )
        else:
            print("  WARNING: Could not find bypass_cache in function sig")
            return False
    else:
        # No bypass_cache - add at end
        # Find the last param line
        lines = current_sig.split("\n")
        last_param_idx = len(lines) - 1
        if not lines[last_param_idx].rstrip().endswith(","):
            lines[last_param_idx] = lines[last_param_idx].rstrip() + ","
        bool_block_lines = bool_kwargs
        new_sig = "\n".join(lines + bool_block_lines) + "\n"

    content = content[:func_sig_start] + new_sig + content[func_sig_end:]

    # 6. Add booleans to cache_key dict
    # Find the cache_key dict
    cache_dict_match = re.search(
        r"(    cache_key_val = cache_key\(\s*\"[^\"]+\",\s*\{)(.*?)(\s*\},?\s*\))",
        content,
        re.DOTALL,
    )
    if cache_dict_match:
        cache_dict_content = cache_dict_match.group(2)
        cache_dict_end = cache_dict_match.end(2)

        # Add boolean entries
        bool_cache_entries = []
        for b in booleans:
            bool_cache_entries.append(f'            "{b}": {b},')

        # Ensure the last existing entry has a trailing comma
        existing_entries = cache_dict_content.rstrip()
        if not existing_entries.endswith(","):
            # Find and fix the last entry
            last_comma_or_entry = existing_entries.rfind('"')
            if last_comma_or_entry != -1:
                # More robust: just ensure trailing comma
                pass

        bool_cache_block = "\n" + "\n".join(bool_cache_entries)
        content = content[:cache_dict_end] + bool_cache_block + content[cache_dict_end:]

    # 7. Replace SqlParams construction with handcrafted Params
    # Find the params = SearchXSqlParams(...) block
    old_params_pattern = rf"    params = {sql_params_class}\(\s*(.*?)\s*\)"
    old_params_match = re.search(old_params_pattern, content, re.DOTALL)

    if old_params_match:
        # Build new params construction
        new_params_entries = []
        if is_id_list_pattern:
            new_params_entries.append(f"        {id_list_param}={id_list_param} or [],")
            if "limit_count" in func_params_str:
                new_params_entries.append("        limit_count=limit_count,")
            if "offset_count" in func_params_str:
                new_params_entries.append("        offset_count=offset_count,")
        else:
            new_params_entries.append("        search=search,")
            new_params_entries.append("        limit_count=limit_count,")
            new_params_entries.append("        offset_count=offset_count,")
            if has_user_department_ids:
                new_params_entries.append(
                    "        user_department_ids=user_department_ids or [],"
                )
            if has_draft_id:
                new_params_entries.append("        draft_id=draft_id,")
            if has_suggest_source:
                new_params_entries.append("        suggest_source=suggest_source,")
            if has_exclude_ids:
                new_params_entries.append("        exclude_ids=exclude_ids or [],")

        for b in booleans:
            new_params_entries.append(f"        {b}={b},")

        new_params_block = (
            f"    params = {params_class_name}(\n"
            + "\n".join(new_params_entries)
            + "\n    )"
        )
        content = (
            content[: old_params_match.start()]
            + new_params_block
            + content[old_params_match.end() :]
        )

    # 8. Handle flags special case: remove artifact_type from cache_key and params
    if has_artifact_type:
        content = content.replace('            "artifact_type": artifact_type,\n', "")
        content = content.replace("        artifact_type=artifact_type,\n", "")

    with open(py_file, "w") as f:
        f.write(content)

    print(f"  Python transformed: {len(booleans)} booleans added")
    return True


# ============================================================================
# ARTIFACT CALLER TRANSFORMATION
# ============================================================================


# Maps artifact -> resource -> line patterns to update
def transform_artifact_callers(resource, booleans):
    """Update artifact get.py callers to add boolean kwargs."""
    artifacts_dir = os.path.join(BASE_DIR, "server/app/api/v4/artifacts")

    # Find all artifact get.py files that import this resource's search
    import_pattern = (
        f"from app.api.v4.resources.{resource}.search import search_{resource}_internal"
    )
    count = 0

    for artifact in os.listdir(artifacts_dir):
        get_file = os.path.join(artifacts_dir, artifact, "get.py")
        if not os.path.isfile(get_file):
            continue

        with open(get_file) as f:
            content = f.read()

        if import_pattern not in content:
            continue

        # Check if already transformed
        if f"{artifact}=True" in content and f"search_{resource}_internal" in content:
            # Verify it's for this specific search function
            search_call_idx = content.find(f"search_{resource}_internal")
            if search_call_idx != -1:
                # Check nearby for artifact=True
                nearby = content[search_call_idx : search_call_idx + 500]
                if f"{artifact}=True" in nearby:
                    print(f"    {artifact}/get.py already updated, skipping")
                    continue

        # Only update if this artifact has a boolean for this resource
        if artifact not in booleans:
            continue

        modified = False

        # For flags: replace artifact_type="..." with {artifact}=True
        if resource == "flags":
            old_pattern = f'artifact_type="{artifact}"'
            if old_pattern in content:
                content = content.replace(old_pattern, f"{artifact}=True")
                modified = True

        # For descriptions/departments/other resources with suggest_source:
        # Add {artifact}=True keyword arg to the call
        # Find calls to search_{resource}_internal
        call_pattern = f"search_{resource}_internal("
        idx = 0
        while True:
            idx = content.find(call_pattern, idx)
            if idx == -1:
                break

            # Find the end of this function call (matching parens)
            paren_depth = 0
            call_start = idx
            i = idx + len(call_pattern) - 1  # position of opening paren
            while i < len(content):
                if content[i] == "(":
                    paren_depth += 1
                elif content[i] == ")":
                    paren_depth -= 1
                    if paren_depth == 0:
                        call_end = i + 1
                        break
                i += 1
            else:
                break

            call_text = content[call_start:call_end]

            # Check if already has the boolean
            if f"{artifact}=True" in call_text:
                idx = call_end
                continue

            # Add the boolean kwarg before the closing paren
            # Find the last non-whitespace before closing paren
            inner = call_text[:-1].rstrip()
            if not inner.endswith(","):
                inner += ","
            new_call = inner + f"\n                {artifact}=True,\n            )"
            content = content[:call_start] + new_call + content[call_end:]
            modified = True

            # Adjust idx for next iteration
            idx = call_start + len(new_call)

        if modified:
            with open(get_file, "w") as f:
                f.write(content)
            count += 1
            print(f"    {artifact}/get.py updated with {artifact}=True")

    if count == 0:
        print("  No artifact callers needed updating")
    else:
        print(f"  Updated {count} artifact caller(s)")


# ============================================================================
# MAIN
# ============================================================================


def main():
    print("=" * 70)
    print("Applying boolean filter pattern to all resource SEARCH endpoints")
    print("=" * 70)

    total_sql = 0
    total_py = 0
    total_callers = 0
    errors = []

    for resource, booleans in sorted(RESOURCE_BOOLEANS.items()):
        if resource in SKIP_RESOURCES:
            continue

        if not booleans:
            continue

        print(f"\n--- {resource} ({len(booleans)} booleans) ---")

        # Transform SQL
        try:
            if transform_sql(resource, booleans):
                total_sql += 1
        except Exception as e:
            errors.append(f"SQL {resource}: {e}")
            print(f"  ERROR in SQL: {e}")

        # Transform Python
        try:
            if transform_python(resource, booleans):
                total_py += 1
        except Exception as e:
            errors.append(f"Python {resource}: {e}")
            print(f"  ERROR in Python: {e}")

        # Transform artifact callers
        try:
            transform_artifact_callers(resource, booleans)
        except Exception as e:
            errors.append(f"Callers {resource}: {e}")
            print(f"  ERROR in callers: {e}")

    print(f"\n{'=' * 70}")
    print(f"SUMMARY: {total_sql} SQL files, {total_py} Python files transformed")
    if errors:
        print(f"\nERRORS ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    print("=" * 70)


if __name__ == "__main__":
    main()
