"""runs/search — filtered/paginated query against runs_mv."""

from datetime import datetime, timezone
from uuid import UUID

import asyncpg  # type: ignore
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.utils.cache.hedged_row import hedged_search_with_total

MV_NAME = "runs_mv"


class RunPricingItem(BaseModel):
    """Single pricing entry for a run. Cost computed at runtime."""

    pricing_type: str | None = Field(None, description="Type of pricing (e.g. input, output, cached)")
    count: int = Field(0, description="Token count for this pricing type")
    pricing_id: UUID | None = Field(None, description="UUID of the pricing configuration")


class RunViewItem(BaseModel):
    """Single run from the run list."""

    run_id: UUID = Field(..., description="UUID of the run")
    group_id: UUID | None = Field(None, description="UUID of the owning group")
    profiles_id: UUID | None = Field(None, description="UUID of the profile that created the run")
    input_tokens: int = Field(0, description="Number of input tokens used")
    output_tokens: int = Field(0, description="Number of output tokens generated")
    cached_input_tokens: int = Field(0, description="Number of cached input tokens")
    run_created_at: datetime | None = Field(None, description="Run creation timestamp")
    agent_ids: list[UUID] | None = Field(None, description="Agent UUIDs involved in the run")
    model_ids: list[UUID] | None = Field(None, description="Model UUIDs used in the run")
    provider_ids: list[UUID] | None = Field(None, description="Provider UUIDs used in the run")
    pricing: list[RunPricingItem] = Field(default_factory=list, description="Pricing breakdown entries")


class GetRunListViewResponse(BaseModel):
    """Response containing run list data."""

    items: list[RunViewItem] = Field(default_factory=list, description="Run data items")
    total_count: int = Field(default=0, description="Total count before pagination")


def _build_pricing_list(item: object) -> list[RunPricingItem]:
    """Build pricing list from flat columns."""

    def _value(field: str):
        if hasattr(item, "__getitem__"):
            try:
                return item[field]  # type: ignore[index]
            except (KeyError, IndexError, TypeError):
                pass
        return getattr(item, field, None)

    pricing: list[RunPricingItem] = []
    if _value("input_pricing_count") is not None:
        pricing.append(
            RunPricingItem(
                pricing_type="input",
                count=_value("input_pricing_count") or 0,
                pricing_id=_value("input_pricing_pricing_id"),
            )
        )
    if _value("output_pricing_count") is not None:
        pricing.append(
            RunPricingItem(
                pricing_type="output",
                count=_value("output_pricing_count") or 0,
                pricing_id=_value("output_pricing_pricing_id"),
            )
        )
    if _value("cached_pricing_count") is not None:
        pricing.append(
            RunPricingItem(
                pricing_type="cached",
                count=_value("cached_pricing_count") or 0,
                pricing_id=_value("cached_pricing_pricing_id"),
            )
        )
    return pricing


def _pricing_from_cache(raw: object) -> list[RunPricingItem]:
    """Hydrate pricing from a cached row's serialized list (list[dict])."""
    if not raw:
        return []
    out: list[RunPricingItem] = []
    for item in raw:
        if isinstance(item, RunPricingItem):
            out.append(item)
        elif isinstance(item, dict):
            out.append(RunPricingItem.model_validate(item))
    return out


async def search_runs(
    conn: asyncpg.Connection,
    redis: Redis,
    group_ids: list[UUID] | None = None,
    profiles_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_order: str = "desc",
    soft: bool = False,
    mcp: bool | None = None,
    has_models: bool = False,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> tuple[list[RunViewItem], int]:
    """Search runs from runs_mv with declarative filters.

    Hedged: merges the MV result with the write-back cache (see
    ``hedged_search_with_total``) so freshly-created runs appear before
    the MV refresh has caught up. Cache rows default token counts to 0
    and model/provider/pricing aggregates to empty — junction writes
    (tokens_entry, run_pricing_entry, runs_agents_connection) must
    invalidate the parent run-id row to surface the real aggregates.

    Returns (items, total_count). When has_models=True, only runs with
    at least one model_id are returned — used by the test picker to
    drop runs that aren't usable as benchmark configs.
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    order = "ASC" if sort_order.lower() == "asc" else "DESC"

    rows = await conn.fetch(
        f"""
        SELECT run_id, group_id, profiles_id,
               input_tokens, output_tokens, cached_input_tokens,
               run_created_at,
               agent_ids, model_ids, provider_ids,
               input_pricing_count, input_pricing_pricing_id,
               output_pricing_count, output_pricing_pricing_id,
               cached_pricing_count, cached_pricing_pricing_id,
               COUNT(*) OVER() AS total_count
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR group_id = ANY($1))
          AND ($2::uuid[] IS NULL OR profiles_id = ANY($2))
          AND ($3::timestamptz IS NULL OR run_created_at >= $3)
          AND ($4::timestamptz IS NULL OR run_created_at <= $4)
          AND (NOT $7::boolean OR (model_ids IS NOT NULL AND array_length(model_ids, 1) > 0))
        ORDER BY run_created_at {order}
        LIMIT $5 OFFSET $6
        """,
        group_ids,
        profiles_ids,
        date_from,
        date_to,
        limit + offset + 1000,
        0,
        has_models,
    )

    mv_total = rows[0]["total_count"] if rows else 0

    # Reshape MV rows to match cache-row keyspace (str ids, isoformat ts,
    # pricing as list[dict] of RunPricingItem.model_dump shape).
    def _pricing_dicts(r: object) -> list[dict]:
        return [p.model_dump(mode="json") for p in _build_pricing_list(r)]

    mv_dicts = [
        {
            "run_id": str(r["run_id"]),
            "group_id": str(r["group_id"]) if r["group_id"] else None,
            "profiles_id": str(r["profiles_id"]) if r["profiles_id"] else None,
            "input_tokens": r["input_tokens"] or 0,
            "output_tokens": r["output_tokens"] or 0,
            "cached_input_tokens": r["cached_input_tokens"] or 0,
            "run_created_at": (
                r["run_created_at"].isoformat()
                if isinstance(r["run_created_at"], datetime)
                else r["run_created_at"]
            ),
            "agent_ids": (
                [str(a) for a in r["agent_ids"]] if r["agent_ids"] else None
            ),
            "model_ids": (
                [str(m) for m in r["model_ids"]] if r["model_ids"] else None
            ),
            "provider_ids": (
                [str(p) for p in r["provider_ids"]] if r["provider_ids"] else None
            ),
            "pricing": _pricing_dicts(r),
        }
        for r in rows
    ]

    group_ids_str = {str(g) for g in group_ids} if group_ids else None
    profiles_ids_str = {str(p) for p in profiles_ids} if profiles_ids else None

    def matches(row: dict) -> bool:
        if group_ids_str is not None and str(row.get("group_id")) not in group_ids_str:
            return False
        if profiles_ids_str is not None and str(row.get("profiles_id")) not in profiles_ids_str:
            return False
        ts = row.get("run_created_at")
        ts_dt: datetime | None = None
        if isinstance(ts, str):
            try:
                ts_dt = datetime.fromisoformat(ts)
            except ValueError:
                ts_dt = None
        elif isinstance(ts, datetime):
            ts_dt = ts
        if date_from is not None and ts_dt is not None and ts_dt < date_from:
            return False
        if date_to is not None and ts_dt is not None and ts_dt > date_to:
            return False
        if has_models:
            mids = row.get("model_ids")
            if not mids:
                return False
        return True

    def _sort_key(row: dict) -> datetime:
        ts = row.get("run_created_at")
        if ts is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        return ts

    # ASC pagination doesn't compose with the helper's DESC-internal sort;
    # fall back to MV-only for ASC requests.
    if sort_order.lower() == "asc":
        mv_dicts.sort(key=_sort_key)
        page = mv_dicts[offset : offset + limit]
        items = [
            RunViewItem(
                run_id=UUID(d["run_id"]),
                group_id=UUID(d["group_id"]) if d.get("group_id") else None,
                profiles_id=UUID(d["profiles_id"]) if d.get("profiles_id") else None,
                input_tokens=d.get("input_tokens", 0),
                output_tokens=d.get("output_tokens", 0),
                cached_input_tokens=d.get("cached_input_tokens", 0),
                run_created_at=d.get("run_created_at"),
                agent_ids=(
                    [UUID(a) for a in d["agent_ids"]] if d.get("agent_ids") else None
                ),
                model_ids=(
                    [UUID(m) for m in d["model_ids"]] if d.get("model_ids") else None
                ),
                provider_ids=(
                    [UUID(p) for p in d["provider_ids"]]
                    if d.get("provider_ids")
                    else None
                ),
                pricing=_pricing_from_cache(d.get("pricing")),
            )
            for d in page
        ]
        return items, mv_total

    merged, total = await hedged_search_with_total(
        redis,
        "runs",
        mv_rows=mv_dicts,
        mv_total=mv_total,
        matches_filter=matches,
        sort_key=_sort_key,
        limit=limit,
        offset=offset,
        id_key="run_id",
        bypass_cache=bypass_cache,
    )

    items = [
        RunViewItem(
            run_id=UUID(d["run_id"]),
            group_id=UUID(d["group_id"]) if d.get("group_id") else None,
            profiles_id=UUID(d["profiles_id"]) if d.get("profiles_id") else None,
            input_tokens=d.get("input_tokens", 0),
            output_tokens=d.get("output_tokens", 0),
            cached_input_tokens=d.get("cached_input_tokens", 0),
            run_created_at=d.get("run_created_at"),
            agent_ids=(
                [UUID(a) for a in d["agent_ids"]] if d.get("agent_ids") else None
            ),
            model_ids=(
                [UUID(m) for m in d["model_ids"]] if d.get("model_ids") else None
            ),
            provider_ids=(
                [UUID(p) for p in d["provider_ids"]]
                if d.get("provider_ids")
                else None
            ),
            pricing=_pricing_from_cache(d.get("pricing")),
        )
        for d in merged
    ]
    return items, total
