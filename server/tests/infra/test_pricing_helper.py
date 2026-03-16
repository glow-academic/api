"""Tests for infra.pricing."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.infra.pricing import compute_costs_from_runs
from app.tools.entries.runs.search import RunPricingItem, RunViewItem
from app.tools.resources.pricing.create import create_pricing

pytestmark = pytest.mark.asyncio


async def test_compute_costs_from_runs_batches_pricing(conn, redis_client):
    input_pricing = await create_pricing(
        conn,
        "input",
        0.02,
        "tokens",
        "tokens",
        1000,
        redis_client,
    )
    output_pricing = await create_pricing(
        conn,
        "output",
        0.03,
        "tokens",
        "tokens",
        1000,
        redis_client,
    )

    run_id = uuid4()
    runs = [
        RunViewItem(
            run_id=run_id,
            pricing=[
                RunPricingItem(
                    pricing_type="input", count=1500, pricing_id=input_pricing.id
                ),
                RunPricingItem(
                    pricing_type="output", count=2000, pricing_id=output_pricing.id
                ),
            ],
        )
    ]

    result = await compute_costs_from_runs(conn, runs, bypass_cache=True)

    assert result[run_id].quantize(Decimal("0.01")) == Decimal("0.09")


async def test_compute_costs_skips_missing_pricing_info(conn):
    run_id = uuid4()
    runs = [
        RunViewItem(
            run_id=run_id,
            pricing=[
                RunPricingItem(pricing_type="input", count=1000, pricing_id=uuid4()),
                RunPricingItem(pricing_type="output", count=0, pricing_id=uuid4()),
            ],
        )
    ]

    result = await compute_costs_from_runs(conn, runs, bypass_cache=True)

    assert result[run_id] == Decimal("0")


async def test_compute_costs_returns_empty_for_no_runs(conn):
    result = await compute_costs_from_runs(conn, [], bypass_cache=True)

    assert result == {}
