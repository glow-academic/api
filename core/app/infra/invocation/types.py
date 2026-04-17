"""Handcrafted types for invocation artifact (operational view of benchmark).

Invocation is to benchmark what training is to home: the operational/execution layer.
Includes Suite/Bundle types for the customization flow and socket generation layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.resource_type_filter import ScopedItem
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


class SectionFilter(BaseModel):
    """Per-section filter options for GET requests."""

    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")
    parameter_ids: list[str] | None = Field(
        None,
        description="Reserved for compatibility with shared filter parsing",
    )


class InvocationNameResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationDescriptionResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationValueResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    value: str | None = Field(None, description="Value text")
    type: str | None = Field(None, description="Value type")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationFlagResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Human-readable flag label")
    description: str | None = Field(None, description="Flag description text")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="UUID of the selected flag option")
    show: bool = Field(True, description="Whether the flag is visible to the client")
    required: bool = Field(False, description="Whether the flag is required")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationDepartmentResource(BaseModel):
    department_id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationKeyResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    key_id: UUID | None = Field(None, description="Resource identifier alias for picker compatibility")
    name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description text")
    key_masked: str | None = Field(None, description="Masked key preview")
    masked_key: str | None = Field(None, description="Masked key preview alias")
    active: bool | None = Field(None, description="Whether this key is active")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationEndpointResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    base_url: str | None = Field(None, description="Endpoint base URL")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationModalityResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    modality_id: UUID | None = Field(None, description="Resource identifier alias for picker compatibility")
    modality: str | None = Field(None, description="Modality code")
    name: str | None = Field(None, description="Human-readable modality name")
    description: str | None = Field(None, description="Description text")
    is_input: bool | None = Field(None, description="Whether this modality is input-facing")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationTemperatureLevelResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    temperature: float | None = Field(None, description="Temperature numeric value")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationPricingResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    pricing_id: UUID | None = Field(None, description="Resource identifier alias for picker compatibility")
    pricing_type: str | None = Field(None, description="Pricing type")
    price: float | None = Field(None, description="Price amount")
    unit_name: str | None = Field(None, description="Unit name")
    unit_category: str | None = Field(None, description="Unit category")
    unit_value: int | None = Field(None, description="Unit value")
    name: str | None = Field(None, description="Display label")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationReasoningLevelResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    reasoning_level: str | None = Field(None, description="Reasoning level label")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationQualityResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    quality_id: UUID | None = Field(None, description="Resource identifier alias for picker compatibility")
    quality: str | None = Field(None, description="Quality label")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class InvocationVoiceResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    voice: str | None = Field(None, description="Voice label")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class GetInvocationApiRequest(BaseModel):
    """Request model for invocation GET."""

    id: UUID | None = Field(None, description="Invocation identifier")
    invocation_id: UUID | None = Field(None, description="Invocation identifier")
    benchmark_bundle_entry_id: UUID | None = Field(None, description="Legacy invocation identifier")
    test_id: UUID | None = Field(None, description="Owning test identifier")
    draft_id: UUID | None = Field(None, description="Optional draft identifier")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions section")
    values: SectionFilter | None = Field(None, description="Filter options for values section")
    flags: SectionFilter | None = Field(None, description="Filter options for flags section")
    departments: SectionFilter | None = Field(None, description="Filter options for departments section")
    keys: SectionFilter | None = Field(None, description="Filter options for keys section")
    endpoints: SectionFilter | None = Field(None, description="Filter options for endpoints section")
    modalities: SectionFilter | None = Field(None, description="Filter options for modalities section")
    temperature_levels: SectionFilter | None = Field(None, description="Filter options for temperature levels section")
    pricing: SectionFilter | None = Field(None, description="Filter options for pricing section")
    reasoning_levels: SectionFilter | None = Field(None, description="Filter options for reasoning levels section")
    qualities: SectionFilter | None = Field(None, description="Filter options for qualities section")
    voices: SectionFilter | None = Field(None, description="Filter options for voices section")
    descriptions_search: str | None = Field(None, description="Legacy search string for descriptions")


GetSuiteRequest = GetInvocationApiRequest


class GetSuiteResponse(BaseModel):
    """Client-facing invocation bundle response using the canonical flat shape."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    test_id: UUID | None = Field(None, description="Owning test identifier")
    invocation_id: UUID | None = Field(None, description="Invocation identifier")
    profile_has_access: bool = Field(False, description="Whether profile has access")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this invocation draft")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled, if any")
    group_id: UUID | None = Field(None, description="Associated group ID")
    show_ai_generate: bool | None = Field(None, description="Whether to show AI generate anywhere")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")
    names: list[InvocationNameResource] | None = Field(None, description="Name resources")
    descriptions: list[InvocationDescriptionResource] | None = Field(None, description="Description resources")
    values: list[InvocationValueResource] | None = Field(None, description="Value resources")
    flags: list[InvocationFlagResource] | None = Field(None, description="Flag resources")
    departments: list[InvocationDepartmentResource] | None = Field(None, description="Department resources")
    keys: list[InvocationKeyResource] | None = Field(None, description="Key resources")
    endpoints: list[InvocationEndpointResource] | None = Field(None, description="Endpoint resources")
    modalities: list[InvocationModalityResource] | None = Field(None, description="Modality resources")
    temperature_levels: list[InvocationTemperatureLevelResource] | None = Field(None, description="Temperature level resources")
    pricing: list[InvocationPricingResource] | None = Field(None, description="Pricing resources")
    reasoning_levels: list[InvocationReasoningLevelResource] | None = Field(None, description="Reasoning level resources")
    qualities: list[InvocationQualityResource] | None = Field(None, description="Quality resources")
    voices: list[InvocationVoiceResource] | None = Field(None, description="Voice resources")


# =============================================================================
# DRAFT endpoint types (composable infra)
# =============================================================================


class SaveInvocationFieldError(BaseModel):
    """Error for a specific field during invocation draft save."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message")


class PatchInvocationDraftApiRequest(ScopedItem):
    """Request model for canonical invocation draft updates."""

    draft_id: UUID | None = Field(None, description="Existing draft identifier to update")
    input_draft_id: UUID | None = Field(None, description="Legacy alias for draft_id")

    name: str | None = Field(None, description="Name value to create")
    name_id: UUID | None = Field(None, description="Selected name identifier")
    description: str | None = Field(None, description="Description value to create")
    description_id: UUID | None = Field(None, description="Selected description identifier")

    value_id: UUID | None = Field(None, description="Selected value identifier")
    flag_ids: list[UUID] | None = Field(None, description="Selected flag identifiers")
    department_ids: list[UUID] | None = Field(None, description="Selected department identifiers")
    key_id: UUID | None = Field(None, description="Selected key identifier")
    endpoint_id: UUID | None = Field(None, description="Selected endpoint identifier")
    modality_ids: list[UUID] | None = Field(None, description="Selected modality identifiers")
    temperature_level_id: UUID | None = Field(None, description="Selected temperature level identifier")
    pricing_id: UUID | None = Field(None, description="Selected pricing identifier")
    reasoning_level_id: UUID | None = Field(None, description="Selected reasoning level identifier")
    quality_ids: list[UUID] | None = Field(None, description="Selected quality identifiers")
    voice_ids: list[UUID] | None = Field(None, description="Selected voice identifiers")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep pending where supported")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack-style replay")
    accept: bool = Field(True, description="Accept or reject a dormant change when used with idempotency_key")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "value_id": "values",
        "flag_ids": "flags",
        "department_ids": "departments",
        "key_id": "keys",
        "endpoint_id": "endpoints",
        "modality_ids": "modalities",
        "temperature_level_id": "temperature_levels",
        "pricing_id": "pricing",
        "reasoning_level_id": "reasoning_levels",
        "quality_ids": "qualities",
        "voice_ids": "voices",
    }


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Saved name identifier")
    name: str | None = Field(None, description="Saved name value")
    description_id: UUID | None = Field(None, description="Saved description identifier")
    description: str | None = Field(None, description="Saved description value")
    value_id: UUID | None = Field(None, description="Saved value identifier")
    flag_ids: list[UUID] = Field(default_factory=list, description="Saved flag identifiers")
    department_ids: list[UUID] = Field(default_factory=list, description="Saved department identifiers")
    key_id: UUID | None = Field(None, description="Saved key identifier")
    endpoint_id: UUID | None = Field(None, description="Saved endpoint identifier")
    modality_ids: list[UUID] = Field(default_factory=list, description="Saved modality identifiers")
    temperature_level_id: UUID | None = Field(None, description="Saved temperature level identifier")
    pricing_id: UUID | None = Field(None, description="Saved pricing identifier")
    reasoning_level_id: UUID | None = Field(None, description="Saved reasoning level identifier")
    quality_ids: list[UUID] = Field(default_factory=list, description="Saved quality identifiers")
    voice_ids: list[UUID] = Field(default_factory=list, description="Saved voice identifiers")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


InvocationDraftFormState = DraftFormState


class PatchInvocationDraftApiResponse(BaseModel):
    """Response model for canonical invocation draft endpoint."""

    success: bool = Field(..., description="Whether the save succeeded")
    draft_id: UUID = Field(..., description="Draft identifier")
    idempotency_key: UUID | None = Field(None, description="Operation key echoed back when present")
    message: str = Field(..., description="Status message")
    form_state: DraftFormState | None = Field(None, description="Authoritative form state after save")


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


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsInvocationApiRequest(BaseModel):
    """Request model for invocation generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsInvocationListItem(BaseModel):
    """Single generation group in the invocation generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsInvocationApiResponse(BaseModel):
    """Response model for invocation generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsInvocationListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemInvocationApiRequest(BaseModel):
    """Request model for invocation problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")


class ProblemInvocationApiResponse(BaseModel):
    """Response model for invocation problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
