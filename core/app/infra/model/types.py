"""Handcrafted types for model artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.model_drafts.types import GetModelDraftResponse

# =============================================================================
# Flag Config
# =============================================================================


class ModelFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Human-readable flag label")
    description: str | None = Field(None, description="Flag description")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="Option ID to use when enabling")
    show: bool = Field(True, description="Whether to display this flag in the UI")
    required: bool = Field(False, description="Whether this flag is required")
    generated: bool | None = Field(None, description="Whether this flag was AI-generated")


# =============================================================================
# GET Endpoint Types — canonical composed API
# =============================================================================


class ModelNameResource(BaseModel):
    id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Model display name")
    generated: bool | None = Field(None, description="Whether the name was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ModelDescriptionResource(BaseModel):
    id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Model description")
    generated: bool | None = Field(None, description="Whether the description was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ModelValueResource(BaseModel):
    id: UUID | None = Field(None, description="Value resource identifier")
    value: str | None = Field(None, description="Model value")
    value_type: str | None = Field(None, description="Stored value type")
    generated: bool | None = Field(None, description="Whether the value was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ModelProviderResource(BaseModel):
    id: UUID | None = Field(None, description="Provider resource identifier")
    name: str | None = Field(None, description="Provider display name")
    description: str | None = Field(None, description="Provider description")
    value: str | None = Field(None, description="Provider value")
    base_url: str | None = Field(None, description="Provider endpoint")
    generated: bool | None = Field(None, description="Whether the provider was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ModelDepartmentResource(BaseModel):
    department_id: UUID | None = Field(None, description="Department identifier")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether the department was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ModelModalityResource(BaseModel):
    id: UUID | None = Field(None, description="Modality resource identifier")
    modality: str | None = Field(None, description="Modality name")
    is_input: bool | None = Field(None, description="Whether this is an input modality")
    generated: bool | None = Field(None, description="Whether the modality was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ModelTemperatureLevelResource(BaseModel):
    id: UUID | None = Field(None, description="Temperature level resource identifier")
    temperature: str | None = Field(None, description="Temperature level label")
    generated: bool | None = Field(None, description="Whether the temperature level was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ModelPricingResource(BaseModel):
    id: UUID | None = Field(None, description="Pricing resource identifier")
    pricing_type: str | None = Field(None, description="Pricing type")
    price: float | None = Field(None, description="Pricing amount")
    unit_name: str | None = Field(None, description="Pricing unit name")
    unit_category: str | None = Field(None, description="Pricing unit category")
    unit_value: float | None = Field(None, description="Pricing unit value")
    generated: bool | None = Field(None, description="Whether the pricing resource was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ModelReasoningLevelResource(BaseModel):
    id: UUID | None = Field(None, description="Reasoning level resource identifier")
    reasoning_level: str | None = Field(None, description="Reasoning level label")
    generated: bool | None = Field(None, description="Whether the reasoning level was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ModelQualityResource(BaseModel):
    id: UUID | None = Field(None, description="Quality resource identifier")
    quality: str | None = Field(None, description="Quality label")
    generated: bool | None = Field(None, description="Whether the quality was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ModelVoiceResource(BaseModel):
    id: UUID | None = Field(None, description="Voice resource identifier")
    voice: str | None = Field(None, description="Voice label")
    generated: bool | None = Field(None, description="Whether the voice was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SectionFilter(BaseModel):
    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")


class GetModelApiRequest(BaseModel):
    id: UUID | None = Field(None, description="Model unique identifier")
    model_id: UUID | None = Field(None, description="Legacy alias for model unique identifier")
    draft_id: UUID | None = Field(None, description="Draft unique identifier")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions")
    values: SectionFilter | None = Field(None, description="Filter options for values")
    providers: SectionFilter | None = Field(None, description="Filter options for providers")
    flags: SectionFilter | None = Field(None, description="Filter options for flags")
    departments: SectionFilter | None = Field(None, description="Filter options for departments")
    modalities: SectionFilter | None = Field(None, description="Filter options for modalities")
    temperature_levels: SectionFilter | None = Field(None, description="Filter options for temperature levels")
    pricing: SectionFilter | None = Field(None, description="Filter options for pricing")
    reasoning_levels: SectionFilter | None = Field(None, description="Filter options for reasoning levels")
    qualities: SectionFilter | None = Field(None, description="Filter options for qualities")
    voices: SectionFilter | None = Field(None, description="Filter options for voices")


class GetModelApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current actor")
    model_exists: bool | None = Field(None, description="Whether the model exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    group_id: UUID | None = Field(None, description="Group identifier for the model")
    model_id: UUID | None = Field(None, description="Model identifier")
    show_ai_generate: bool | None = Field(None, description="Whether any step should show AI generate")
    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    provider_show_ai_generate: bool | None = Field(None, description="Show AI generate for provider step")
    features_show_ai_generate: bool | None = Field(None, description="Show AI generate for features step")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")

    names: list[ModelNameResource] | None = Field(None, description="Name resources")
    descriptions: list[ModelDescriptionResource] | None = Field(None, description="Description resources")
    values: list[ModelValueResource] | None = Field(None, description="Value resources")
    providers: list[ModelProviderResource] | None = Field(None, description="Provider resources")
    flags: list[ModelFlagConfig] | None = Field(None, description="Flag configs")
    departments: list[ModelDepartmentResource] | None = Field(None, description="Department resources")
    modalities: list[ModelModalityResource] | None = Field(None, description="Modality resources")
    temperature_levels: list[ModelTemperatureLevelResource] | None = Field(None, description="Temperature level resources")
    pricing: list[ModelPricingResource] | None = Field(None, description="Pricing resources")
    reasoning_levels: list[ModelReasoningLevelResource] | None = Field(None, description="Reasoning level resources")
    qualities: list[ModelQualityResource] | None = Field(None, description="Quality resources")
    voices: list[ModelVoiceResource] | None = Field(None, description="Voice resources")


# =============================================================================
# LIST Endpoint Types
# =============================================================================


class ListModelApiModel(BaseModel):
    """Model type for list endpoint with computed permissions."""

    model_id: UUID | None = Field(None, description="Model unique identifier")
    name: str | None = Field(None, description="Display name of the model")
    description: str | None = Field(None, description="Model description text")
    provider_id: UUID | None = Field(None, description="Associated provider identifier")
    provider_name: str | None = Field(None, description="Associated provider display name")
    base_url: str | None = Field(None, description="Base URL for the model API")
    department_ids: list[str] | None = Field(None, description="Associated department identifiers")
    is_inactive: bool | None = Field(None, description="Whether the model is inactive")
    active: bool | None = Field(None, description="Whether the model is currently active")
    image_model: bool | None = Field(None, description="Whether this is an image model")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    updated_at: datetime | None = Field(None, description="Timestamp of last update")


class ListModelApiResponse(BaseModel):
    """Response model for list model endpoint with computed permissions."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    models: list[ListModelApiModel] | None = Field(None, description="List of model entries")
    provider_filter: ListFilterSection | None = Field(None, description="Provider filter options")
    department_filter: ListFilterSection | None = Field(None, description="Department filter options")
    agent_filter: ListFilterSection | None = Field(None, description="Agent filter options")
    total_count: int | None = Field(None, description="Total number of models")


# =============================================================================
# Shared Create/Update Types
# =============================================================================


class ModelFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class ModelResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    model_id: UUID | None = Field(None, description="Model unique identifier")
    message: str = Field(..., description="Result message")
    errors: list[ModelFieldError] | None = Field(None, description="List of field-level errors")


# =============================================================================
# Create Endpoint Types
# =============================================================================


class CreateModelItem(ScopedItem):
    """Single model item for create — no model_id.

    Required fields (name): provide ID or value.
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "department_ids": "departments",
        "departments": "departments",
        "active_flag": "flags",
        "active_flag_id": "flags",
        "flag_ids": "flags",
        "modality_ids": "modalities",
        "pricing_ids": "pricing",
        "provider_id": "providers",
        "quality_ids": "qualities",
        "reasoning_level_ids": "reasoning_levels",
        "temperature_level_ids": "temperature_levels",
        "value_id": "values",
        "voice_ids": "voices",
        "model_ids": "models",
    }

    id: UUID | None = Field(None, description="Optional pre-assigned identifier")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Dual-mode: name
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    # Dual-mode: departments (match by name)
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    departments: list[str] | None = Field(None, description="Department names to match")
    # Active flag
    active_flag: bool | None = Field(None, description="Whether this model is active")
    active_flag_id: UUID | None = Field(None, description="Active flag resource UUID")
    # ID-only fields
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    modality_ids: list[UUID] | None = Field(None, description="Modality identifiers")
    pricing_ids: list[UUID] | None = Field(None, description="Pricing tier identifiers")
    provider_id: UUID | None = Field(None, description="Provider identifier")
    quality_ids: list[UUID] | None = Field(None, description="Quality level identifiers")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Reasoning level identifiers")
    temperature_level_ids: list[UUID] | None = Field(None, description="Temperature level identifiers")
    value_id: UUID | None = Field(None, description="Value resource identifier")
    value: str | None = Field(None, description="Direct model value/identifier (e.g. the actual API model name)")
    voice_ids: list[UUID] | None = Field(None, description="Voice identifiers")
    model_ids: list[UUID] | None = Field(None, description="Related model identifiers")


class CreateModelApiRequest(BaseModel):
    """Request model for bulk create model endpoint."""

    models: list[CreateModelItem] = Field(..., description="List of models to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateModelApiResponse(BaseModel):
    """Response model for bulk create model endpoint."""

    results: list[ModelResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# =============================================================================
# Update Endpoint Types
# =============================================================================


class UpdateModelItem(ScopedItem):
    """Single model item for update — model_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateModelItem.RESOURCE_TYPE_MAP

    model_id: UUID = Field(..., description="Target model identifier to update")
    # Dual-mode: name
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    # Dual-mode: departments (match by name)
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    departments: list[str] | None = Field(None, description="Department names to match")
    # Active flag
    active_flag: bool | None = Field(None, description="Whether this model is active")
    active_flag_id: UUID | None = Field(None, description="Active flag resource UUID")
    # ID-only fields
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    modality_ids: list[UUID] | None = Field(None, description="Modality identifiers")
    pricing_ids: list[UUID] | None = Field(None, description="Pricing tier identifiers")
    provider_id: UUID | None = Field(None, description="Provider identifier")
    quality_ids: list[UUID] | None = Field(None, description="Quality level identifiers")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Reasoning level identifiers")
    temperature_level_ids: list[UUID] | None = Field(None, description="Temperature level identifiers")
    value_id: UUID | None = Field(None, description="Value resource identifier")
    voice_ids: list[UUID] | None = Field(None, description="Voice identifiers")
    model_ids: list[UUID] | None = Field(None, description="Related model identifiers")


class UpdateModelApiRequest(BaseModel):
    """Request model for bulk update model endpoint."""

    models: list[UpdateModelItem] = Field(..., description="List of models to update")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateModelApiResponse(BaseModel):
    """Response model for bulk update model endpoint."""

    results: list[ModelResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveModelFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


# =============================================================================
# DELETE Endpoint Types (unchanged)
# =============================================================================


class DeleteModelApiRequest(BaseModel):
    """Request model for bulk delete model endpoint."""

    model_ids: list[UUID] = Field(..., description="List of model IDs to delete")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool = Field(True, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteModelResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    model_id: UUID = Field(..., description="Deleted model identifier")
    message: str = Field(..., description="Result message")


class DeleteModelApiResponse(BaseModel):
    """Response model for bulk delete model endpoint."""

    results: list[DeleteModelResult] = Field(..., description="List of deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# =============================================================================
# DUPLICATE Endpoint Types (unchanged)
# =============================================================================


class DuplicateModelApiRequest(BaseModel):
    """Request model for duplicate model endpoint."""

    model_id: UUID = Field(..., description="Model identifier to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateModelApiResponse(BaseModel):
    """Response model for duplicate model endpoint."""

    success: bool = Field(..., description="Whether the duplication succeeded")
    model_id: UUID = Field(..., description="New duplicated model identifier")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# =============================================================================
# DRAFT Endpoint Types (composable infra)
# =============================================================================


class PatchModelDraftApiRequest(ScopedItem):
    """Request model for canonical model draft endpoint."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "value": "values",
        "value_id": "values",
        "provider": "providers",
        "provider_id": "providers",
        "departments": "departments",
        "flag_ids": "flags",
        "department_ids": "departments",
        "active_flag": "flags",
        "active_flag_id": "flags",
        "modalities_enabled_flag_id": "flags",
        "temperature_enabled_flag_id": "flags",
        "pricing_enabled_flag_id": "flags",
        "voices_enabled_flag_id": "flags",
        "reasoning_levels_enabled_flag_id": "flags",
        "qualities_enabled_flag_id": "flags",
        "modalities": "modalities",
        "modality_ids": "modalities",
        "pricing": "pricing",
        "pricing_ids": "pricing",
        "qualities": "qualities",
        "reasoning_levels": "reasoning_levels",
        "temperature_levels": "temperature_levels",
        "voices": "voices",
        "provider_id": "providers",
        "quality_ids": "qualities",
        "reasoning_level_ids": "reasoning_levels",
        "temperature_level_ids": "temperature_levels",
        "voice_ids": "voices",
    }

    draft_id: UUID | None = Field(None, description="Existing draft ID to update")
    input_draft_id: UUID | None = Field(None, description="Existing draft ID to update")
    idempotency_key: UUID | None = Field(None, description="Operation key for accept/reject style ack")
    accept: bool = Field(True, description="Accept or reject when idempotency_key is supplied")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name value")
    name_id: UUID | None = Field(None, description="Name resource identifier")
    description: str | None = Field(None, description="Description text value")
    description_id: UUID | None = Field(None, description="Description resource identifier")
    value: str | None = Field(None, description="Direct model value")
    value_id: UUID | None = Field(None, description="Value resource identifier")
    provider: str | None = Field(None, description="Provider name to match")
    provider_id: UUID | None = Field(None, description="Provider identifier")

    # Matchable / multi-select
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    active_flag: bool | None = Field(None, description="Whether the model is active")
    active_flag_id: UUID | None = Field(None, description="Active flag resource identifier")
    modalities_enabled_flag_id: UUID | None = Field(None, description="Modalities enabled flag resource identifier")
    temperature_enabled_flag_id: UUID | None = Field(None, description="Temperature enabled flag resource identifier")
    pricing_enabled_flag_id: UUID | None = Field(None, description="Pricing enabled flag resource identifier")
    voices_enabled_flag_id: UUID | None = Field(None, description="Voices enabled flag resource identifier")
    reasoning_levels_enabled_flag_id: UUID | None = Field(None, description="Reasoning levels enabled flag resource identifier")
    qualities_enabled_flag_id: UUID | None = Field(None, description="Qualities enabled flag resource identifier")
    departments: list[str] | None = Field(None, description="Department names to match")
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    modalities: list[str] | None = Field(None, description="Modality labels to match")
    modality_ids: list[UUID] | None = Field(None, description="Modality identifiers")
    pricing: list[str] | None = Field(None, description="Pricing types to match")
    pricing_ids: list[UUID] | None = Field(None, description="Pricing tier identifiers")
    qualities: list[str] | None = Field(None, description="Quality labels to match")
    quality_ids: list[UUID] | None = Field(None, description="Quality level identifiers")
    reasoning_levels: list[str] | None = Field(None, description="Reasoning level labels to match")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Reasoning level identifiers")
    temperature_levels: list[str] | None = Field(None, description="Temperature level labels to match")
    temperature_level_ids: list[UUID] | None = Field(None, description="Temperature level identifiers")
    voices: list[str] | None = Field(None, description="Voice labels to create or match")
    voice_ids: list[UUID] | None = Field(None, description="Voice identifiers")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers")


class DraftFormState(BaseModel):
    name_id: UUID | None = Field(None, description="Resolved name resource identifier")
    name: str | None = Field(None, description="Resolved name value")
    description_id: UUID | None = Field(None, description="Resolved description resource identifier")
    description: str | None = Field(None, description="Resolved description value")
    value_id: UUID | None = Field(None, description="Resolved value resource identifier")
    value: str | None = Field(None, description="Resolved model value")
    provider_id: UUID | None = Field(None, description="Resolved provider identifier")
    provider: str | None = Field(None, description="Resolved provider name")
    flag_ids: list[UUID] = Field(..., description="Flag option identifiers")
    active_flag_id: UUID | None = Field(None, description="Resolved active flag identifier")
    modalities_enabled_flag_id: UUID | None = Field(None, description="Resolved modalities enabled flag identifier")
    temperature_enabled_flag_id: UUID | None = Field(None, description="Resolved temperature enabled flag identifier")
    pricing_enabled_flag_id: UUID | None = Field(None, description="Resolved pricing enabled flag identifier")
    voices_enabled_flag_id: UUID | None = Field(None, description="Resolved voices enabled flag identifier")
    reasoning_levels_enabled_flag_id: UUID | None = Field(None, description="Resolved reasoning levels enabled flag identifier")
    qualities_enabled_flag_id: UUID | None = Field(None, description="Resolved qualities enabled flag identifier")
    department_ids: list[UUID] = Field(..., description="Department identifiers")
    modality_ids: list[UUID] = Field(..., description="Modality identifiers")
    pricing_ids: list[UUID] = Field(..., description="Pricing tier identifiers")
    quality_ids: list[UUID] = Field(..., description="Quality level identifiers")
    reasoning_level_ids: list[UUID] = Field(..., description="Reasoning level identifiers")
    temperature_level_ids: list[UUID] = Field(..., description="Temperature level identifiers")
    voice_ids: list[UUID] = Field(..., description="Voice identifiers")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


ModelDraftFormState = DraftFormState


class PatchModelDraftApiResponse(BaseModel):
    """Response model for new-style model draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="Draft unique identifier")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    message: str = Field(..., description="Result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


class GetModelDraftsApiResponse(BaseModel):
    """Response model for model drafts list endpoint."""

    entries: list[GetModelDraftResponse] | None = Field(None, description="List of model draft entries")


# ========== Export Endpoint Types ==========


class ExportModelApiRequest(BaseModel):
    """Request model for model export."""

    model_id: UUID | None = Field(None, description="Model identifier to export")


class ExportModelApiResponse(BaseModel):
    """Response model for export model endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsModelApiRequest(BaseModel):
    """Request model for model generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsModelListItem(BaseModel):
    """Single generation group in the model generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsModelApiResponse(BaseModel):
    """Response model for model generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsModelListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemModelApiRequest(BaseModel):
    """Request model for model problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemModelApiResponse(BaseModel):
    """Response model for model problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
