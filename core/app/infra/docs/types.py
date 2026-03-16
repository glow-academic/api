"""Shared Pydantic models for entry/resource/artifact documentation."""

from typing import Any

from pydantic import BaseModel, Field

from app.infra.docs_helper import DocsApiResponse


class ColumnInfo(BaseModel):
    name: str = Field(..., description="Column name")
    type: str = Field(..., description="Column data type")
    nullable: bool = Field(..., description="Whether the column is nullable")


class MvInfo(BaseModel):
    name: str = Field(..., description="Materialized view name")
    definition: str = Field(..., description="SQL definition of the view")
    columns: list[ColumnInfo] = Field(..., description="List of columns in the view")


class TableInfo(BaseModel):
    name: str = Field(..., description="Table name")
    columns: list[ColumnInfo] = Field(..., description="List of columns in the table")


class ParamInfo(BaseModel):
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter data type")
    required: bool = Field(..., description="Whether the parameter is required")
    default: Any | None = Field(None, description="Default value if not required")


class OperationInfo(BaseModel):
    name: str = Field(..., description="Operation name")
    description: str = Field(..., description="Human-readable description of the operation")
    params: list[ParamInfo] = Field(..., description="List of operation parameters")
    returns: dict[str, Any] | None = Field(None, description="Return type schema")


class DocsResponse(BaseModel):
    name: str = Field(..., description="Resource or entry name")
    type: str = Field(..., description="Resource or entry type identifier")
    description: str = Field(..., description="Human-readable description")
    materialized_view: MvInfo | None = Field(None, description="Materialized view metadata")
    tables: list[TableInfo] = Field(..., description="Related database tables")
    operations: list[OperationInfo] = Field(..., description="Available operations")


class ComposedDocsResponse(BaseModel):
    """Composed documentation for a full artifact endpoint.

    Aggregates the artifact tool docs, entry docs, resource docs,
    permission functions, and infra operations into one response.
    """

    name: str = Field(..., description="Artifact name")
    type: str = Field(..., description="Artifact type identifier")
    description: str = Field(..., description="Human-readable description")
    artifact: DocsResponse | None = Field(None, description="Artifact tool documentation")
    entries: list[DocsResponse] = Field(..., description="Entry documentation list")
    resources: list[DocsResponse] = Field(..., description="Resource documentation list")
    permissions: list[OperationInfo] = Field(..., description="Permission function documentation")
    api_operations: list[OperationInfo] = Field(..., description="API operation documentation")
    page_metadata: DocsApiResponse | None = Field(None, description="Page-level metadata from docs API")
