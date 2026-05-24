"""Tests for pricing shared helpers."""
import pytest
from decimal import Decimal
from app.infra.pricing.shared import PricingInfo
pytestmark = pytest.mark.asyncio

async def test_pricing_info_creation():
    p = PricingInfo(price=Decimal("0.50"), unit_value=1000)
    assert p.price == Decimal("0.50")
    assert p.unit_value == 1000

async def test_pricing_info_slots():
    p = PricingInfo(price=Decimal("1.00"), unit_value=500)
    assert hasattr(p, "price")
    assert hasattr(p, "unit_value")

async def test_compute_costs_is_async():
    from app.infra.pricing.shared import compute_costs_from_runs
    import asyncio
    assert asyncio.iscoroutinefunction(compute_costs_from_runs)
