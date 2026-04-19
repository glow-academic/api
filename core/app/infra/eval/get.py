"""Canonical shared eval GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.eval.context import resolve_eval_context
from app.infra.eval.permissions import (
    EVAL_BASIC_RESOURCES,
    EVAL_MODEL_RESOURCES,
    EVAL_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_model_flags_required,
    compute_model_positions_required,
    compute_model_rubrics_required,
    compute_models_required,
    compute_name_required,
    compute_show_active_flag,
    compute_show_departments,
    compute_show_description,
    compute_show_groups_flag,
    compute_show_model_flags,
    compute_show_model_positions,
    compute_show_model_rubrics,
    compute_show_models,
    compute_show_name,
    has_access,
)
from app.infra.eval.permissions_context import resolve_eval_permissions_context
from app.infra.eval.types import (
    EvalDepartmentResource,
    EvalDescriptionResource,
    EvalFlagConfig,
    EvalModelFlagResource,
    EvalModelPositionResource,
    EvalModelResource,
    EvalModelRubricResource,
    EvalNameResource,
    GetEvalApiResponse,
    SectionFilter,
)
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import score_tools

SECTIONS = [
    "names",
    "descriptions",
    "flags",
    "departments",
    "models",
    "model_flags",
    "model_rubrics",
    "model_positions",
]


def _sf(filters: dict[str, SectionFilter | None], section: str, attr: str, default=None):
    section_filter = filters.get(section)
    if section_filter is None:
        return default
    return getattr(section_filter, attr, default)


def _filter_items(items: list | None, section: str, *, selected_only: dict[str, bool], suggested_only: dict[str, bool]):
    if items is None:
        return None
    result = items
    if selected_only.get(section):
        result = [item for item in result if getattr(item, "selected", False)]
    if suggested_only.get(section):
        result = [item for item in result if getattr(item, "suggested", False)]
    return result


def _derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("eval_", "")
    return (key, key.replace("_", " ").title())


async def get_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    eval_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetEvalApiResponse:
    """Resolve the canonical eval artifact bundle for any surface."""

    eval_id = id or eval_id
    resolved_filters = dict(filters or {})

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="eval",
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    profile = common.profile
    effective_group_id = group_id or profile.group_id

    perms = None
    if eval_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_eval_permissions_context(conn, eval_id)
        if not perms.exists:
            raise HTTPException(status_code=404, detail=f"Eval {eval_id} not found")
        if not has_access(profile.role_level, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this eval. It may be restricted to other departments.",
            )

    eval_ctx = await resolve_eval_context(
        pool,
        redis,
        eval_id=eval_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        departments_search=_sf(resolved_filters, "departments", "search"),
        models_search=_sf(resolved_filters, "models", "search"),
        model_flags_search=_sf(resolved_filters, "model_flags", "search"),
        model_rubrics_search=_sf(resolved_filters, "model_rubrics", "search"),
        model_positions_search=_sf(resolved_filters, "model_positions", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        departments_limit=_sf(resolved_filters, "departments", "limit"),
        models_limit=_sf(resolved_filters, "models", "limit"),
        model_flags_limit=_sf(resolved_filters, "model_flags", "limit"),
        model_rubrics_limit=_sf(resolved_filters, "model_rubrics", "limit"),
        model_positions_limit=_sf(resolved_filters, "model_positions", "limit"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, EVAL_RESOURCES)
    include = {
        section: _sf(resolved_filters, section, "include") is not False
        for section in SECTIONS
    }
    selected_only = {
        section: bool(_sf(resolved_filters, section, "selected"))
        for section in SECTIONS
    }
    suggested_only = {
        section: bool(_sf(resolved_filters, section, "suggested"))
        for section in SECTIONS
    }

    can_edit = compute_can_edit(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    )
    disabled_reason = compute_disabled_reason(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    )

    pending_ids: set[UUID] = eval_ctx.entries.get("pending_ids", set())

    names_selected = eval_ctx.resources["names"].selected
    names_suggestions = eval_ctx.resources["names"].suggestions
    descriptions_selected = eval_ctx.resources["descriptions"].selected
    descriptions_suggestions = eval_ctx.resources["descriptions"].suggestions
    flags_selected = eval_ctx.resources["flags"].selected
    flags_suggestions = eval_ctx.resources["flags"].suggestions
    departments_selected = eval_ctx.resources["departments"].selected
    departments_suggestions = eval_ctx.resources["departments"].suggestions
    models_selected = eval_ctx.resources["models"].selected
    models_suggestions = eval_ctx.resources["models"].suggestions
    model_flags_selected = eval_ctx.resources["model_flags"].selected
    model_flags_suggestions = eval_ctx.resources["model_flags"].suggestions
    model_rubrics_selected = eval_ctx.resources["model_rubrics"].selected
    model_rubrics_suggestions = eval_ctx.resources["model_rubrics"].suggestions
    model_positions_selected = eval_ctx.resources["model_positions"].selected
    model_positions_suggestions = eval_ctx.resources["model_positions"].suggestions

    all_names = dedupe_by_id(names_selected + names_suggestions)
    all_descriptions = dedupe_by_id(descriptions_selected + descriptions_suggestions)
    all_flags = dedupe_by_id(flags_selected + flags_suggestions)
    all_departments = dedupe_by_id(departments_selected + departments_suggestions)
    all_models = dedupe_by_id(models_selected + models_suggestions)
    all_model_flags = dedupe_by_id(model_flags_selected + model_flags_suggestions)
    all_model_rubrics = dedupe_by_id(model_rubrics_selected + model_rubrics_suggestions)
    all_model_positions = dedupe_by_id(model_positions_selected + model_positions_suggestions)

    selected_ids = {
        "names": {item.id for item in names_selected if item.id},
        "descriptions": {item.id for item in descriptions_selected if item.id},
        "flags": {item.id for item in flags_selected if item.id},
        "departments": {getattr(item, "department_id", None) for item in departments_selected if getattr(item, "department_id", None)},
        "models": {item.id for item in models_selected if item.id},
        "model_flags": {item.id for item in model_flags_selected if item.id},
        "model_rubrics": {item.id for item in model_rubrics_selected if item.id},
        "model_positions": {item.id for item in model_positions_selected if item.id},
    }
    suggested_ids = {
        "names": {item.id for item in names_suggestions if item.id},
        "descriptions": {item.id for item in descriptions_suggestions if item.id},
        "flags": {item.id for item in flags_suggestions if item.id},
        "departments": {getattr(item, "department_id", None) for item in departments_suggestions if getattr(item, "department_id", None)},
        "models": {item.id for item in models_suggestions if item.id},
        "model_flags": {item.id for item in model_flags_suggestions if item.id},
        "model_rubrics": {item.id for item in model_rubrics_suggestions if item.id},
        "model_positions": {item.id for item in model_positions_suggestions if item.id},
    }

    show_flags_map = {
        "names": compute_show_name(scores.has_any.get("names", False)),
        "descriptions": compute_show_description(),
        "flags": compute_show_active_flag() or compute_show_groups_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "models": compute_show_models(len(all_models)),
        "model_flags": compute_show_model_flags(len(all_model_flags)),
        "model_rubrics": compute_show_model_rubrics(len(all_model_rubrics)),
        "model_positions": compute_show_model_positions(len(all_model_positions)),
    }
    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": False,
        "departments": compute_departments_required(show_flags_map["departments"]),
        "models": compute_models_required(),
        "model_flags": compute_model_flags_required(),
        "model_rubrics": compute_model_rubrics_required(),
        "model_positions": compute_model_positions_required(),
    }

    def _decorate(item_id: UUID | None, section: str) -> tuple[bool, bool, bool]:
        return (
            bool(item_id and item_id in suggested_ids[section]),
            bool(item_id and item_id in selected_ids[section]),
            bool(item_id and item_id in pending_ids),
        )

    names = [
        EvalNameResource(
            id=item.id,
            name=item.name,
            generated=item.generated,
            suggested=_decorate(item.id, "names")[0],
            selected=_decorate(item.id, "names")[1],
            pending=_decorate(item.id, "names")[2],
        )
        for item in all_names
    ]
    descriptions = [
        EvalDescriptionResource(
            id=item.id,
            description=item.description,
            generated=item.generated,
            suggested=_decorate(item.id, "descriptions")[0],
            selected=_decorate(item.id, "descriptions")[1],
            pending=_decorate(item.id, "descriptions")[2],
        )
        for item in all_descriptions
    ]
    flags = [
        EvalFlagConfig(
            key=_derive_flag_key_and_label(getattr(item, "name", None) or getattr(item, "type", None))[0],
            label=_derive_flag_key_and_label(getattr(item, "name", None) or getattr(item, "type", None))[1],
            description=item.description,
            icon_id=getattr(item, "icon_id", None),
            flag_option_id=item.id,
            show=show_flags_map["flags"],
            required=required_flags_map["flags"],
            generated=item.generated,
            suggested=_decorate(item.id, "flags")[0],
            selected=_decorate(item.id, "flags")[1],
            pending=_decorate(item.id, "flags")[2],
        )
        for item in all_flags
    ]
    departments = [
        EvalDepartmentResource(
            department_id=getattr(item, "department_id", None),
            name=item.name,
            description=item.description,
            generated=item.generated,
            suggested=_decorate(getattr(item, "department_id", None), "departments")[0],
            selected=_decorate(getattr(item, "department_id", None), "departments")[1],
            pending=_decorate(getattr(item, "department_id", None), "departments")[2],
        )
        for item in all_departments
    ]
    models = [
        EvalModelResource(
            id=item.id,
            name=item.name,
            description=item.description,
            modality_ids=getattr(item, "modality_ids", None),
            generated=item.generated,
            suggested=_decorate(item.id, "models")[0],
            selected=_decorate(item.id, "models")[1],
            pending=_decorate(item.id, "models")[2],
        )
        for item in all_models
    ]
    model_flags = [
        EvalModelFlagResource(
            id=item.id,
            model_id=getattr(item, "model_id", None),
            flag_id=getattr(item, "flag_id", None),
            name=item.name,
            description=item.description,
            icon=getattr(item, "icon", None),
            generated=item.generated,
            suggested=_decorate(item.id, "model_flags")[0],
            selected=_decorate(item.id, "model_flags")[1],
            pending=_decorate(item.id, "model_flags")[2],
        )
        for item in all_model_flags
    ]
    model_rubrics = [
        EvalModelRubricResource(
            id=item.id,
            model_id=getattr(item, "model_id", None),
            rubric_id=getattr(item, "rubric_id", None),
            generated=item.generated,
            suggested=_decorate(item.id, "model_rubrics")[0],
            selected=_decorate(item.id, "model_rubrics")[1],
            pending=_decorate(item.id, "model_rubrics")[2],
        )
        for item in all_model_rubrics
    ]
    model_positions = [
        EvalModelPositionResource(
            id=item.id,
            model_id=getattr(item, "model_id", None),
            value=getattr(item, "value", None),
            generated=item.generated,
            suggested=_decorate(item.id, "model_positions")[0],
            selected=_decorate(item.id, "model_positions")[1],
            pending=_decorate(item.id, "model_positions")[2],
        )
        for item in all_model_positions
    ]

    return GetEvalApiResponse(
        actor_name=profile.actor_name,
        eval_exists=perms.exists if perms else None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        basic_show_ai_generate=any(scores.has_any.get(section, False) for section in EVAL_BASIC_RESOURCES),
        model_show_ai_generate=any(scores.has_any.get(section, False) for section in EVAL_MODEL_RESOURCES),
        show_ai_generate=any(scores.has_any.values()),
        pending_ids=sorted(pending_ids) or None,
        names=_filter_items(names, "names", selected_only=selected_only, suggested_only=suggested_only) if include["names"] else None,
        descriptions=_filter_items(descriptions, "descriptions", selected_only=selected_only, suggested_only=suggested_only) if include["descriptions"] else None,
        flags=_filter_items(flags, "flags", selected_only=selected_only, suggested_only=suggested_only) if include["flags"] else None,
        departments=_filter_items(departments, "departments", selected_only=selected_only, suggested_only=suggested_only) if include["departments"] else None,
        models=_filter_items(models, "models", selected_only=selected_only, suggested_only=suggested_only) if include["models"] else None,
        model_flags=_filter_items(model_flags, "model_flags", selected_only=selected_only, suggested_only=suggested_only) if include["model_flags"] else None,
        model_rubrics=_filter_items(model_rubrics, "model_rubrics", selected_only=selected_only, suggested_only=suggested_only) if include["model_rubrics"] else None,
        model_positions=_filter_items(model_positions, "model_positions", selected_only=selected_only, suggested_only=suggested_only) if include["model_positions"] else None,
    )
