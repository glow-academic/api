"""Tests for shared subscription validation for event delivery transports."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.stream.shared import resolve_subscription

pytestmark = pytest.mark.asyncio(loop_scope="session")


@dataclass
class _FakeOperationConfig:
    scope: str = "entity"
    can_subscribe: object = None


@dataclass
class _FakeArtifactEventsConfig:
    artifact: str = "simulation"
    event_types: tuple = ("started", "completed", "progress")

    def get_operation(self, operation: str):
        if operation == "get":
            return _FakeOperationConfig(
                scope="entity",
                can_subscribe=AsyncMock(return_value=True),
            )
        return None


async def test_resolve_subscription_raises_404_for_unknown_artifact():
    """Unknown artifact raises 404."""
    with patch(
        "app.infra.stream.shared.get_artifact_events_config",
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await resolve_subscription(
                artifact="nonexistent",
                operation="get",
                entity_id=uuid4(),
                profile_id=uuid4(),
                session_id=uuid4(),
            )

    assert exc_info.value.status_code == 404
    assert "No event registry" in exc_info.value.detail


async def test_resolve_subscription_raises_404_for_unknown_operation():
    """Unknown operation on a known artifact raises 404."""
    config = _FakeArtifactEventsConfig()

    with patch(
        "app.infra.stream.shared.get_artifact_events_config",
        return_value=config,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await resolve_subscription(
                artifact="simulation",
                operation="nonexistent-op",
                entity_id=uuid4(),
                profile_id=uuid4(),
                session_id=uuid4(),
            )

    assert exc_info.value.status_code == 404
    assert "No event operation" in exc_info.value.detail


async def test_resolve_subscription_raises_400_when_entity_id_missing():
    """Entity-scoped operations require entity_id."""
    config = _FakeArtifactEventsConfig()

    with patch(
        "app.infra.stream.shared.get_artifact_events_config",
        return_value=config,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await resolve_subscription(
                artifact="simulation",
                operation="get",
                entity_id=None,
                profile_id=uuid4(),
                session_id=uuid4(),
            )

    assert exc_info.value.status_code == 400
    assert "entity_id is required" in exc_info.value.detail


async def test_resolve_subscription_raises_401_when_profile_missing():
    """Missing profile_id raises 401."""
    config = _FakeArtifactEventsConfig()

    with patch(
        "app.infra.stream.shared.get_artifact_events_config",
        return_value=config,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await resolve_subscription(
                artifact="simulation",
                operation="get",
                entity_id=uuid4(),
                profile_id=None,
                session_id=uuid4(),
            )

    assert exc_info.value.status_code == 401
    assert "Profile ID is required" in exc_info.value.detail


async def test_resolve_subscription_raises_400_for_invalid_event_types():
    """Unsupported event types raise 400."""
    config = _FakeArtifactEventsConfig()

    with patch(
        "app.infra.stream.shared.get_artifact_events_config",
        return_value=config,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await resolve_subscription(
                artifact="simulation",
                operation="get",
                entity_id=uuid4(),
                profile_id=uuid4(),
                session_id=uuid4(),
                event_types=["bogus_event"],
            )

    assert exc_info.value.status_code == 400
    assert "Unsupported event types" in exc_info.value.detail


async def test_resolve_subscription_raises_403_when_denied():
    """Access denied raises 403."""
    op_config = _FakeOperationConfig(
        scope="entity",
        can_subscribe=AsyncMock(return_value=False),
    )
    config = MagicMock()
    config.get_operation.return_value = op_config
    config.event_types = ("started", "completed")

    with patch(
        "app.infra.stream.shared.get_artifact_events_config",
        return_value=config,
    ):
        with patch("app.infra.stream.shared.get_pool", return_value=MagicMock()):
            with patch(
                "app.infra.stream.shared.get_redis_client",
                return_value=AsyncMock(),
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await resolve_subscription(
                        artifact="simulation",
                        operation="get",
                        entity_id=uuid4(),
                        profile_id=uuid4(),
                        session_id=uuid4(),
                    )

    assert exc_info.value.status_code == 403


async def test_resolve_subscription_success():
    """Returns config tuple on successful validation."""
    op_config = _FakeOperationConfig(
        scope="entity",
        can_subscribe=AsyncMock(return_value=True),
    )
    config = MagicMock()
    config.get_operation.return_value = op_config
    config.event_types = ("started", "completed")

    with patch(
        "app.infra.stream.shared.get_artifact_events_config",
        return_value=config,
    ):
        with patch("app.infra.stream.shared.get_pool", return_value=MagicMock()):
            with patch(
                "app.infra.stream.shared.get_redis_client",
                return_value=AsyncMock(),
            ):
                art_config, op = await resolve_subscription(
                    artifact="simulation",
                    operation="get",
                    entity_id=uuid4(),
                    profile_id=uuid4(),
                    session_id=uuid4(),
                )

    assert art_config is config
    assert op is op_config
