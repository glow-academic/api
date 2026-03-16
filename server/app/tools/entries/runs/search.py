"""runs/search — filtered/paginated query against runs_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from pydantic import BaseModel, Field

from app.infra.docs.resolve_mv_source import resolve_mv_source

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


async def search_runs(
    conn: asyncpg.Connection,
    group_ids: list[UUID] | None = None,
    profiles_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_order: str = "desc",
    soft: bool = False,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> tuple[list[RunViewItem], int]:
    """Search runs from runs_mv with declarative filters.

    Returns (items, total_count).
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
        ORDER BY run_created_at {order}
        LIMIT $5 OFFSET $6
        """,
        group_ids,
        profiles_ids,
        date_from,
        date_to,
        limit,
        offset,
    )

    total_count = rows[0]["total_count"] if rows else 0
    items = [
        RunViewItem(
            run_id=r["run_id"],
            group_id=r["group_id"],
            profiles_id=r["profiles_id"],
            input_tokens=r["input_tokens"] or 0,
            output_tokens=r["output_tokens"] or 0,
            cached_input_tokens=r["cached_input_tokens"] or 0,
            run_created_at=r["run_created_at"],
            agent_ids=list(r["agent_ids"]) if r["agent_ids"] else None,
            model_ids=list(r["model_ids"]) if r["model_ids"] else None,
            provider_ids=list(r["provider_ids"]) if r["provider_ids"] else None,
            pricing=_build_pricing_list(r),
        )
        for r in rows
    ]
    return (items, total_count)
