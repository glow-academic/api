"""Document artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.document.types import GetDocumentsResponse

TABLE = "document_artifact"
ARTIFACT_FK = "document_id"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "document_names_junction", "names_id", "name_ids"),
    (
        "descriptions",
        "document_descriptions_junction",
        "descriptions_id",
        "description_ids",
    ),
    (
        "departments",
        "document_departments_junction",
        "departments_id",
        "department_ids",
    ),
    ("flags", "document_flags_junction", "flags_id", "flag_ids"),
    ("files", "document_files_junction", "files_id", "files_ids"),
    ("images", "document_images_junction", "images_id", "images_ids"),
    (
        "parameter_fields",
        "document_parameter_fields_junction",
        "parameter_fields_id",
        "parameter_field_ids",
    ),
    ("parameters", "document_parameters_junction", "parameters_id", "parameter_ids"),
    ("texts", "document_texts_junction", "texts_id", "texts_ids"),
    ("documents", "document_documents_junction", "documents_id", "document_ids"),
]


async def get_documents(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    descriptions: bool = False,
    departments: bool = False,
    flags: bool = False,
    files: bool = False,
    images: bool = False,
    parameter_fields: bool = False,
    parameters: bool = False,
    texts: bool = False,
    documents: bool = False,
) -> list[GetDocumentsResponse]:
    """Get document artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "descriptions": descriptions,
        "departments": departments,
        "flags": flags,
        "files": files,
        "images": images,
        "parameter_fields": parameter_fields,
        "parameters": parameters,
        "texts": texts,
        "documents": documents,
    }

    active_junctions = [
        (table, col, field) for flag, table, col, field in JUNCTIONS if flags_map[flag]
    ]

    # Build dynamic query
    columns = [
        "p.id",
        "p.created_at",
        "p.updated_at",
        "p.generated",
        "p.mcp",
        "p.active",
    ]
    joins: list[str] = []

    for i, (table, col, field) in enumerate(active_junctions):
        alias = f"j{i}"
        joins.append(
            f"LEFT JOIN {table} {alias} ON {alias}.{ARTIFACT_FK} = p.id AND {alias}.active = true"
        )
        columns.append(
            f"ARRAY_AGG(DISTINCT {alias}.{col}) FILTER (WHERE {alias}.{col} IS NOT NULL) AS {field}"
        )

    where_clauses = ["p.id = ANY($1)"]
    params: list[object] = [ids]
    if active is not None:
        where_clauses.append(f"p.active = ${len(params) + 1}")
        params.append(active)

    query = f"""
        SELECT {", ".join(columns)}
        FROM {TABLE} p
        {" ".join(joins)}
        WHERE {" AND ".join(where_clauses)}
        GROUP BY p.id, p.created_at, p.updated_at, p.generated, p.mcp, p.active
    """

    rows = await conn.fetch(query, *params)

    results = []
    for r in rows:
        data: dict = {
            "id": r["id"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "active": r["active"],
        }
        for _, _, _, field in JUNCTIONS:
            if field in dict(r):
                data[field] = r[field] or []
        results.append(GetDocumentsResponse(**data))

    return results
