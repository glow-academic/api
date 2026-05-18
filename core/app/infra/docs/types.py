"""Shared Pydantic models for entry/resource/artifact documentation."""

from __future__ import annotations

from typing import Any, List
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.docs_helper import DocsApiResponse
from app.infra.profile.types import ThemeBundle
from app.infra.shared_types import QGetProfileContextV4RoleResource


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


# =============================================================================
# Context types — superset of docs + profile identity + evaluated permissions
# =============================================================================


class ProfileSummary(BaseModel):
    """Caller identity derived from JWT — who you are on this page.

    Superset of the old six-field version: now carries everything the client
    needs so that ``/{artifact}/context`` fully replaces ``/profiles/context``
    and the extra ``getLayoutContextData`` round-trip can be dropped.
    """

    # --- Original fields ---
    name: str = Field(..., description="Display name of the authenticated user")
    role: str = Field(..., description="Role name (e.g. 'Super Administrator')")
    role_level: int = Field(..., description="Role hierarchy level (0 = highest privilege)")
    department_ids: list[UUID] = Field(..., description="Departments the user belongs to")
    artifact_access: list[str] = Field(..., description="Artifact types this role can access (sidebar visibility)")
    role_permissions: list[tuple[str, str]] = Field(..., description="Full (artifact, operation) permission tuples for granular page gating")
    is_active: bool = Field(..., description="Whether the user's profile is active")

    # --- New fields (needed by client providers) ---
    id: UUID = Field(..., description="Profile UUID (SocketProvider, ProfileProvider)")
    theme: ThemeBundle | None = Field(None, description="Resolved theme: hex primitives + derived oklch tokens + score thresholds")
    session_id: UUID | None = Field(None, description="Current session UUID")
    is_emulation: bool = Field(False, description="Whether user is in emulation mode (ProfileProvider)")
    role_resources: list[QGetProfileContextV4RoleResource] | None = Field(None, description="All role resources for emulation display (ProfileProvider)")
    scoped_roles: list[str] | None = Field(None, description="Roles the user can emulate (ProfileProvider)")
    active: bool = Field(True, description="Alias for is_active (ProfileProvider uses this name)")


class CallerPermissions(BaseModel):
    """Evaluated permissions for the current caller on this artifact type."""

    can_create: bool = Field(..., description="Whether the caller can create new artifacts")
    can_draft: bool = Field(..., description="Whether the caller can create/update drafts")
    can_duplicate: bool = Field(..., description="Whether the caller can duplicate artifacts")
    # Entity-specific — only populated when entity_id is provided
    has_access: bool | None = Field(None, description="Whether the caller can view this entity")
    can_edit: bool | None = Field(None, description="Whether the caller can edit this entity")
    can_delete: bool | None = Field(None, description="Whether the caller can delete this entity")
    disabled_reason: str | None = Field(None, description="Human-readable reason if editing is disabled")


class StarterPrompt(BaseModel):
    """Starter prompt for the generation panel."""

    title: str = Field(..., description="Short label shown on the button")
    content: str = Field(..., description="Full instruction text inserted when clicked")


class OperationPrompts(BaseModel):
    """Starter prompts keyed by operation name.

    Each key is an operation (e.g. "create", "search", "draft", "export")
    and the value is a list of starter prompts for that operation.
    The client picks from the operations the caller has permission for
    and rotates through them.
    """

    prompts: dict[str, list[StarterPrompt]] = Field(
        default_factory=dict,
        description="Map of operation name to starter prompts",
    )


class ComposedContextResponse(BaseModel):
    """Page bootstrap response — docs + profile identity + evaluated permissions.

    Superset of ComposedDocsResponse. A single call gives the client everything
    it needs to render the page: who you are, what you can do, and the schema.
    """

    name: str = Field(..., description="Artifact name")
    type: str = Field(..., description="Artifact type identifier")
    description: str = Field(..., description="Human-readable description")
    artifact: DocsResponse | None = Field(None, description="Artifact tool documentation")
    entries: list[DocsResponse] = Field(..., description="Entry documentation list")
    resources: list[DocsResponse] = Field(..., description="Resource documentation list")
    permission_docs: list[OperationInfo] = Field(..., description="Permission function signatures (for MCP/dev tooling)")
    api_operations: list[OperationInfo] = Field(..., description="API operation documentation")
    page_metadata: DocsApiResponse | None = Field(None, description="Page-level metadata")
    prompts: OperationPrompts | None = Field(None, description="Starter prompts keyed by operation")
    # Identity + evaluated permissions
    profile: ProfileSummary = Field(..., description="Caller identity from JWT")
    caller_permissions: CallerPermissions = Field(..., description="Evaluated permissions for this caller")
