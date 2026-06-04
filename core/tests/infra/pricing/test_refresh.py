"""Integration tests for ``refresh_pricing_impl``.

Exercises the pricing MV REFRESH orchestrator only — the enqueue contract it
exposes: which views it claims to refresh (``run_pricing_mv``), which cache
tags it invalidates (``pricing`` + ``artifacts``), and the ack lifecycle
(default enqueue vs ``soft`` record-only vs explicit ``accept=False`` reject)
the shared enqueue path drives off the operation/idempotency key.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.infra.pricing.refresh import refresh_pricing_impl

pytestmark = pytest.mark.asyncio


class TestRefreshPricingClient:
    async def test_refreshes_views_and_invalidates_tags(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        result = await refresh_pricing_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.success is True
        assert result.refreshed_views == ["run_pricing_mv"]
        assert result.invalidated_tags == ["pricing", "artifacts"]

    async def test_soft_records_intent_without_enqueueing_views(
        self, pool, redis_client, profile_identity_factory
    ):
        # soft mode busts cache but does NOT claim a view refresh — the ack
        # will run it later.
        profile = await profile_identity_factory()

        result = await refresh_pricing_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            soft=True,
        )

        assert result.success is True
        assert result.refreshed_views == []
        assert result.invalidated_tags == ["pricing", "artifacts"]

    async def test_explicit_reject_with_key_is_a_noop(
        self, pool, redis_client, profile_identity_factory
    ):
        # accept=False + an operation key short-circuits to a no-op: nothing
        # refreshed, nothing invalidated, but the key is echoed back.
        profile = await profile_identity_factory()
        op_key = uuid4()

        result = await refresh_pricing_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            accept=False,
            operation_key=op_key,
        )

        assert result.success is True
        assert result.refreshed_views == []
        assert result.invalidated_tags == []
        assert result.idempotency_key == op_key

    async def test_idempotency_key_is_echoed_back(
        self, pool, redis_client, profile_identity_factory
    ):
        # A supplied operation key threads through to the response so callers
        # can correlate the ack with the enqueue.
        profile = await profile_identity_factory()
        op_key = uuid4()

        result = await refresh_pricing_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            operation_key=op_key,
        )

        assert result.success is True
        assert result.refreshed_views == ["run_pricing_mv"]
        assert result.idempotency_key == op_key
