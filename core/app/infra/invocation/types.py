"""Handcrafted types for invocation artifact (operational view of benchmark).

Invocation is to benchmark what training is to home: the operational/execution layer.
Includes Suite/Bundle types for the customization flow and socket generation layer.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.tools.entries.invocation_drafts.types import (
    GetInvocationDraftResponse,
)

# =============================================================================
# Export Types
# =============================================================================


class GetInvocationDraftsApiResponse(BaseModel):
    """Response model for invocation drafts list endpoint."""

    entries: list[GetInvocationDraftResponse] | None = Field(None, description="List of invocation draft entries")


class ExportInvocationApiResponse(BaseModel):
    """Response model for invocation export."""

    content: str = Field(..., description="Base64-encoded file content")
    file_name: str = Field(..., description="Suggested download file name")
    mime_type: str = Field(..., description="MIME type of the export file")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# GET Request / Response
# =============================================================================


class GetInvocationApiRequest(BaseModel):
    """Request model for get invocation endpoint."""

    benchmark_entry_id: UUID = Field(..., description="Benchmark entry identifier")
    draft_id: UUID | None = Field(None, description="Optional draft identifier")


# =============================================================================
# SUITE/BUNDLE endpoint types (customize flow) — Section-first pattern
# =============================================================================


class GetSuiteRequest(BaseModel):
    """Client API request for one benchmark bundle customization payload."""

    test_id: UUID = Field(..., description="Test identifier")
    draft_id: UUID | None = Field(None, description="Optional draft identifier")
    # Search filters
    descriptions_search: str | None = Field(None, description="Search string for descriptions")


# --- Section types (one per resource) ---


class BaseSuiteSection(BaseModel):
    """Common metadata fields for all benchmark bundle resource sections."""

    show: bool = Field(False, description="Whether section is visible")
    required: bool = Field(False, description="Whether section is required")
    show_ai_generate: bool = Field(False, description="Whether to show AI generate button")


class SuiteNameSection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected name items")
    resources: list[Any] | None = Field(None, description="Available name resources")


class SuiteDescriptionSection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected description items")
    resources: list[Any] | None = Field(None, description="Available description resources")


class SuiteFlagSection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected flag items")
    resources: list[Any] | None = Field(None, description="Available flag resources")


class SuiteDepartmentSection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected department items")
    resources: list[Any] | None = Field(None, description="Available department resources")


class SuiteValueSection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected value items")
    resources: list[Any] | None = Field(None, description="Available value resources")


class SuiteKeySection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected key items")
    resources: list[Any] | None = Field(None, description="Available key resources")


class SuiteEndpointSection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected endpoint items")
    resources: list[Any] | None = Field(None, description="Available endpoint resources")


class SuiteModalitySection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected modality items")
    resources: list[Any] | None = Field(None, description="Available modality resources")


class SuiteTemperatureLevelSection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected temperature levels")
    resources: list[Any] | None = Field(None, description="Available temperature level resources")


class SuitePricingSection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected pricing items")
    resources: list[Any] | None = Field(None, description="Available pricing resources")


class SuiteReasoningLevelSection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected reasoning levels")
    resources: list[Any] | None = Field(None, description="Available reasoning level resources")


class SuiteQualitySection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected quality items")
    resources: list[Any] | None = Field(None, description="Available quality resources")


class SuiteVoiceSection(BaseSuiteSection):
    current: list[Any] | None = Field(None, description="Currently selected voice items")
    resources: list[Any] | None = Field(None, description="Available voice resources")


# --- GET response (section-first) ---


class GetSuiteResponse(BaseModel):
    """Client-facing bundle response — section-first pattern."""

    test_id: UUID = Field(..., description="Test identifier")
    profile_has_access: bool = Field(False, description="Whether profile has access")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Associated group ID")

    # 13 section-first resources
    names: SuiteNameSection | None = Field(None, description="Name section data")
    descriptions: SuiteDescriptionSection | None = Field(None, description="Description section data")
    values: SuiteValueSection | None = Field(None, description="Value section data")
    flags: SuiteFlagSection | None = Field(None, description="Flag section data")
    departments: SuiteDepartmentSection | None = Field(None, description="Department section data")
    keys: SuiteKeySection | None = Field(None, description="Key section data")
    endpoints: SuiteEndpointSection | None = Field(None, description="Endpoint section data")
    modalities: SuiteModalitySection | None = Field(None, description="Modality section data")
    temperature_levels: SuiteTemperatureLevelSection | None = Field(None, description="Temperature level section data")
    pricing: SuitePricingSection | None = Field(None, description="Pricing section data")
    reasoning_levels: SuiteReasoningLevelSection | None = Field(None, description="Reasoning level section data")
    qualities: SuiteQualitySection | None = Field(None, description="Quality section data")
    voices: SuiteVoiceSection | None = Field(None, description="Voice section data")


# =============================================================================
# DRAFT endpoint types (composable infra)
# =============================================================================


class SaveInvocationFieldError(BaseModel):
    """Error for a specific field during invocation draft save."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message")


class PatchInvocationDraftApiRequest(BaseModel):
    """Request model for new-style invocation draft endpoint.

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="Input draft ID to update")
    expected_version: int = Field(0, description="Expected draft version for optimistic lock")

    # Single-select creatables — provide value OR ID
    name: str | None = Field(None, description="Name value to create")
    description: str | None = Field(None, description="Description value to create")

    # All ID-only (matches GET response sections)
    name_ids: list[UUID] | None = Field(None, description="Selected name IDs")
    description_ids: list[UUID] | None = Field(None, description="Selected description IDs")
    value_ids: list[UUID] | None = Field(None, description="Selected value IDs")
    flag_ids: list[UUID] | None = Field(None, description="Selected flag IDs")
    department_ids: list[UUID] | None = Field(None, description="Selected department IDs")
    key_ids: list[UUID] | None = Field(None, description="Selected key IDs")
    endpoint_ids: list[UUID] | None = Field(None, description="Selected endpoint IDs")
    temperature_level_ids: list[UUID] | None = Field(None, description="Selected temperature level IDs")
    pricing_ids: list[UUID] | None = Field(None, description="Selected pricing IDs")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Selected reasoning level IDs")
    voice_ids: list[UUID] | None = Field(None, description="Selected voice IDs")


class InvocationDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_ids: list[UUID] = Field(..., description="Saved name IDs")
    description_ids: list[UUID] = Field(..., description="Saved description IDs")
    value_ids: list[UUID] = Field(..., description="Saved value IDs")
    flag_ids: list[UUID] = Field(..., description="Saved flag IDs")
    department_ids: list[UUID] = Field(..., description="Saved department IDs")
    key_ids: list[UUID] = Field(..., description="Saved key IDs")
    endpoint_ids: list[UUID] = Field(..., description="Saved endpoint IDs")
    temperature_level_ids: list[UUID] = Field(..., description="Saved temperature level IDs")
    pricing_ids: list[UUID] = Field(..., description="Saved pricing IDs")
    reasoning_level_ids: list[UUID] = Field(..., description="Saved reasoning level IDs")
    voice_ids: list[UUID] = Field(..., description="Saved voice IDs")


class PatchInvocationDraftApiResponse(BaseModel):
    """Response model for new-style invocation draft endpoint."""

    success: bool = Field(..., description="Whether the save succeeded")
    draft_id: UUID = Field(..., description="Draft identifier")
    new_version: int = Field(..., description="New draft version after save")
    message: str = Field(..., description="Status message")
    form_state: InvocationDraftFormState | None = Field(None, description="Authoritative form state after save")


# =============================================================================
# Decrypt Endpoint Types
# =============================================================================


class DecryptInvocationKeyApiRequest(BaseModel):
    """Request to decrypt a key scoped to an invocation."""

    invocation_id: UUID = Field(..., description="Invocation identifier")
    key_id: UUID = Field(..., description="Key identifier to decrypt")


class DecryptInvocationKeyApiResponse(BaseModel):
    """Decrypted key response."""

    key: str | None = Field(None, description="Decrypted key value")
    name: str | None = Field(None, description="Key display name")
    actor_name: str | None = Field(None, description="Name of the actor who decrypted")
