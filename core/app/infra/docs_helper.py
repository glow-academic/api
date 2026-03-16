"""Shared documentation helper for artifact and resource docs.

Provides dataclass configs and builder functions to generate dynamic
(DB-backed) and static documentation for all artifacts and resources.
Also provides shared models and business logic for page metadata endpoints.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any
from uuid import UUID

import asyncpg  # type: ignore
from pydantic import BaseModel

# ========== Page Metadata Models ==========


class PageMetaItem(BaseModel):
    title: str
    description: str


class DocsApiRequest(BaseModel):
    entity_id: UUID | None = None


class DocsApiResponse(BaseModel):
    list: PageMetaItem
    detail: PageMetaItem
    new: PageMetaItem


@dataclass
class PageMetadataConfig:
    list_title: str = ""
    list_description: str = ""
    detail_title: str = ""
    detail_description: str = ""
    new_title: str = ""
    new_description: str = ""


def compute_docs_metadata(
    page_config: PageMetadataConfig,
    entity_name: str | None = None,
) -> DocsApiResponse:
    """Compute page metadata from config and optional entity name."""
    detail_title = (
        f"{entity_name} {page_config.detail_title}"
        if entity_name
        else page_config.detail_title
    )
    return DocsApiResponse(
        list=PageMetaItem(
            title=page_config.list_title, description=page_config.list_description
        ),
        detail=PageMetaItem(
            title=detail_title, description=page_config.detail_description
        ),
        new=PageMetaItem(
            title=page_config.new_title, description=page_config.new_description
        ),
    )


# ========== Config Dataclasses ==========


@dataclass
class ArtifactDocsConfig:
    """Configuration for generating artifact documentation."""

    name: str  # singular: "persona"
    plural_name: str  # "personas"
    entity_type: str = "artifact"  # "artifact", "analytics", "workflow"
    table_name: str | None = None  # "persona_artifact" (None for analytics)
    junction_prefix: str | None = None  # "persona" (None for analytics)
    fk_pattern: str | None = None  # "persona_%" (None for analytics)
    permissions_module: ModuleType | None = None
    permission_functions: list[str] = field(default_factory=list)
    api_routing: dict[str, Any] = field(default_factory=dict)
    glow_context: dict[str, Any] = field(default_factory=dict)
    resources_info: list[dict[str, Any]] = field(default_factory=list)
    extra_sections: dict[str, Any] = field(default_factory=dict)
    page_metadata: PageMetadataConfig | None = None


@dataclass
class ResourceDocsConfig:
    """Configuration for generating resource documentation."""

    name: str  # "names"
    table_name: str | None = None  # "names_resource"
    description: str = ""
    glow_context: dict[str, Any] = field(default_factory=dict)
    used_by_artifacts: list[str] = field(default_factory=list)
    extra_sections: dict[str, Any] = field(default_factory=dict)


# ========== Schema Discovery ==========


async def get_table_columns(
    conn: asyncpg.Connection, table_name: str
) -> list[dict[str, Any]]:
    """Get columns for a table from information_schema."""
    rows = await conn.fetch(
        """
        SELECT
            c.column_name::text AS name,
            c.data_type::text AS type,
            (c.is_nullable = 'YES')::boolean AS nullable,
            c.column_default::text AS default_value
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = $1
        ORDER BY c.ordinal_position
        """,
        table_name,
    )
    return [
        {
            "name": row["name"],
            "type": row["type"],
            "nullable": row["nullable"],
            "default": row["default_value"],
        }
        for row in rows
    ]


async def get_junction_tables(
    conn: asyncpg.Connection, prefix: str
) -> list[dict[str, Any]]:
    """Get junction tables and their columns for a given prefix."""
    rows = await conn.fetch(
        """
        SELECT
            t.table_name::text AS name,
            array_agg(c.column_name::text ORDER BY c.ordinal_position) AS columns
        FROM information_schema.tables t
        JOIN information_schema.columns c
            ON t.table_name = c.table_name
            AND t.table_schema = c.table_schema
        WHERE t.table_schema = 'public'
          AND (t.table_name LIKE $1 || '_%_junction'
               OR t.table_name LIKE '%_' || $1 || 's_%')
        GROUP BY t.table_name
        ORDER BY t.table_name
        """,
        prefix,
    )
    return [{"name": row["name"], "columns": row["columns"]} for row in rows]


async def get_foreign_keys(
    conn: asyncpg.Connection, table_pattern: str
) -> list[dict[str, Any]]:
    """Get foreign key relationships for tables matching a pattern."""
    rows = await conn.fetch(
        """
        SELECT
            tc.table_name::text AS table_name,
            kcu.column_name::text AS column_name,
            ccu.table_name::text AS references_table
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND tc.table_name LIKE $1
        ORDER BY tc.table_name, kcu.column_name
        """,
        table_pattern,
    )
    return [
        {
            "table": row["table_name"],
            "column": row["column_name"],
            "references": row["references_table"],
        }
        for row in rows
    ]


# ========== Business Logic Extraction ==========


def _parse_docstring(docstring: str | None) -> dict[str, Any]:
    """Parse docstring into description and rules."""
    if not docstring:
        return {"description": "", "rules": []}

    lines = docstring.strip().split("\n")
    description = lines[0] if lines else ""

    rules = []
    for line in lines:
        line = line.strip()
        if line.startswith("-") or line.startswith("*"):
            rules.append(line.lstrip("-* "))

    return {"description": description, "rules": rules}


def extract_business_logic(
    module: ModuleType, function_names: list[str]
) -> dict[str, dict[str, Any]]:
    """Extract business logic from permission function docstrings and source."""
    result = {}
    for func_name in function_names:
        func = getattr(module, func_name, None)
        if func is None:
            continue
        parsed = _parse_docstring(inspect.getdoc(func))
        result[func_name] = {
            "description": parsed["description"],
            "rules": parsed["rules"],
            "source": inspect.getsource(func),
        }
    return result


# ========== Linked Resources Extraction ==========


def _extract_linked_resources(
    junction_tables: list[dict[str, Any]], prefix: str
) -> list[str]:
    """Extract resource names from junction table names."""
    linked = []
    for jt in junction_tables:
        name = jt["name"]
        if name and name.startswith(f"{prefix}_") and name.endswith("_junction"):
            resource = name[len(prefix) + 1 : -9]  # Remove prefix_ and _junction
            if resource:
                linked.append(resource)
    return linked


# ========== Sync Builders (for MCP, no DB) ==========


def build_artifact_docs_static(config: ArtifactDocsConfig) -> dict[str, Any]:
    """Build artifact documentation from static config only (no DB queries)."""
    docs: dict[str, Any] = {
        "name": config.plural_name,
        "type": config.entity_type,
    }

    if config.table_name:
        docs["database"] = {"table": config.table_name}

    # Business logic (still works without DB -- uses inspect)
    if config.permissions_module and config.permission_functions:
        docs["business_logic"] = extract_business_logic(
            config.permissions_module, config.permission_functions
        )

    if config.api_routing:
        docs["api_routing"] = config.api_routing
    if config.resources_info:
        docs["resources"] = {"available": config.resources_info}
    if config.glow_context:
        docs["glow_context"] = config.glow_context
    for key, value in config.extra_sections.items():
        docs[key] = value

    return docs


def build_resource_docs_static(config: ResourceDocsConfig) -> dict[str, Any]:
    """Build resource documentation from static config only (no DB queries)."""
    docs: dict[str, Any] = {
        "name": config.name,
        "type": "resource",
        "description": config.description,
    }

    if config.table_name:
        docs["database"] = {"table": config.table_name}
    if config.used_by_artifacts:
        docs["used_by_artifacts"] = config.used_by_artifacts
    if config.glow_context:
        docs["glow_context"] = config.glow_context
    for key, value in config.extra_sections.items():
        docs[key] = value

    return docs
