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
    EvalFlagResource,
    EvalModelFlagOptionResource,
    EvalModelFlagResource,
    EvalModelPositionResource,
    EvalModelResource,
    EvalModelRubricResource,
    EvalNameResource,
    EvalRubricResource,
    GetEvalApiResponse,
    SectionFilter,
)
from app.infra.group.resolve import resolve_group_impl
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
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    profile = common.profile
    if group_id is None:
        _gr = await resolve_group_impl(
            pool, redis,
            artifact_type="eval",
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
        group_id = _gr.group_id
    effective_group_id = group_id
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
    # model_flags/rubrics/positions suggestion rows from the context are
    # cross-product entries with `id=None` (no junction row yet). The
    # generic dedupe_by_id drops null ids, which collapses every fresh
    # per-model flag suggestion to nothing. Dedupe by the natural key for
    # each resource instead so the cross-product survives.
    def _dedup_by_keys(items: list, keys: tuple[str, ...]) -> list:
        seen: set[tuple] = set()
        out: list = []
        for item in items:
            key = tuple(getattr(item, k, None) for k in keys)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    all_model_flags = _dedup_by_keys(
        model_flags_selected + model_flags_suggestions, ("model_id", "flag_id")
    )
    all_model_rubrics = _dedup_by_keys(
        model_rubrics_selected + model_rubrics_suggestions,
        ("model_id", "rubric_id"),
    )
    all_model_positions = _dedup_by_keys(
        model_positions_selected + model_positions_suggestions, ("model_id",)
    )

    selected_ids = {
        "names": {item.id for item in names_selected if item.id},
        "descriptions": {item.id for item in descriptions_selected if item.id},
        "flags": {item.id for item in flags_selected if item.id},
        "departments": {item.id for item in departments_selected if item.id},
        "models": {item.id for item in models_selected if item.id},
        "model_flags": {item.id for item in model_flags_selected if item.id},
        "model_rubrics": {item.id for item in model_rubrics_selected if item.id},
        "model_positions": {item.id for item in model_positions_selected if item.id},
    }
    suggested_ids = {
        "names": {item.id for item in names_suggestions if item.id},
        "descriptions": {item.id for item in descriptions_suggestions if item.id},
        "flags": {item.id for item in flags_suggestions if item.id},
        "departments": {item.id for item in departments_suggestions if item.id},
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
        EvalFlagResource(
            id=item.id,
            name=getattr(item, "name", None),
            type=getattr(item, "type", None),
            value=getattr(item, "value", None),
            description=item.description,
            icon_id=getattr(item, "icon_id", None),
            icon=getattr(item, "icon", None),
            generated=item.generated,
            suggested=_decorate(item.id, "flags")[0],
            selected=_decorate(item.id, "flags")[1],
            pending=_decorate(item.id, "flags")[2],
        )
        for item in all_flags
        if item.id
    ]
    departments = [
        EvalDepartmentResource(
            department_id=item.id,
            name=item.name,
            description=item.description,
            generated=item.generated,
            suggested=_decorate(item.id, "departments")[0],
            selected=_decorate(item.id, "departments")[1],
            pending=_decorate(item.id, "departments")[2],
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
    # Cross-product options catalog: for every model × flag_type in
    # MODEL_FLAG_TYPES_ORDERED × value ∈ {true, false}, emit one option row.
    # The client ModelFlags picker groups these by (model_id, type) and
    # renders one Switch per group.
    model_flag_type_rows = eval_ctx.entries.get("model_flag_type_rows", []) or []
    type_by_type: dict[str, object] = {}
    for row in model_flag_type_rows:
        t = getattr(row, "type", None) or getattr(row, "name", None)
        if not t:
            continue
        type_by_type.setdefault(t, row)

    flag_rows_by_type_value: dict[tuple[str, bool], object] = {}
    for row in model_flag_type_rows:
        t = getattr(row, "type", None) or getattr(row, "name", None)
        v = getattr(row, "value", None)
        if t is None or v is None:
            continue
        flag_rows_by_type_value[(t, bool(v))] = row

    # Hydrate each junction-row resource with its (type, value) from the
    # flag catalog — the client Switch groups by (model_id, type).
    def _enrich_junction_type_value(item) -> tuple[str | None, bool | None]:
        fid = getattr(item, "flag_id", None)
        if not fid:
            return (None, None)
        for (t, v), row in flag_rows_by_type_value.items():
            if getattr(row, "id", None) == fid:
                return (t, v)
        return (None, None)

    model_flags = []
    for item in all_model_flags:
        t, v = _enrich_junction_type_value(item)
        model_flags.append(
            EvalModelFlagResource(
                id=item.id,
                model_id=getattr(item, "model_id", None),
                flag_id=getattr(item, "flag_id", None),
                type=t,
                value=v,
                name=item.name,
                description=item.description,
                icon=getattr(item, "icon", None),
                generated=item.generated,
                suggested=_decorate(item.id, "model_flags")[0],
                selected=_decorate(item.id, "model_flags")[1],
                pending=_decorate(item.id, "model_flags")[2],
            )
        )

    selected_model_ids = [
        getattr(m, "id", None) for m in models_selected if getattr(m, "id", None)
    ]
    # Only emit options for currently-selected models to keep the payload
    # bounded; a model landing in `selected` means the user has it in
    # formState.model_ids.
    model_flag_options_list: list[EvalModelFlagOptionResource] = []
    for mid in selected_model_ids:
        for t, catalog_row in type_by_type.items():
            for desired_value in (True, False):
                flag_row = flag_rows_by_type_value.get((t, desired_value))
                if flag_row is None:
                    continue
                model_flag_options_list.append(
                    EvalModelFlagOptionResource(
                        model_id=mid,
                        flag_id=getattr(flag_row, "id", None),
                        type=t,
                        value=desired_value,
                        name=getattr(flag_row, "name", None) or getattr(catalog_row, "name", None),
                        description=getattr(flag_row, "description", None)
                        or getattr(catalog_row, "description", None),
                        icon=getattr(flag_row, "icon", None)
                        or getattr(catalog_row, "icon", None),
                    )
                )
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

    rubrics_pair = eval_ctx.resources.get("rubrics")
    rubrics_catalog = (
        [
            EvalRubricResource(
                id=getattr(r, "id", None),
                name=getattr(r, "name", None),
                description=getattr(r, "description", None),
            )
            for r in rubrics_pair.suggestions
        ]
        if rubrics_pair
        else []
    )

    return GetEvalApiResponse(
        actor_name=profile.name,
        eval_exists=perms.exists if perms else None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        # Draft label sourced from ``entries['draft_name']`` (set by
        # ``resolve_eval_context``). ``None`` when no draft was active.
        draft_name=eval_ctx.entries.get("draft_name") if eval_ctx.entries else None,
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
        model_flag_options=model_flag_options_list if include["model_flags"] else None,
        model_rubrics=_filter_items(model_rubrics, "model_rubrics", selected_only=selected_only, suggested_only=suggested_only) if include["model_rubrics"] else None,
        model_positions=_filter_items(model_positions, "model_positions", selected_only=selected_only, suggested_only=suggested_only) if include["model_positions"] else None,
        rubrics=rubrics_catalog or None,
    )
