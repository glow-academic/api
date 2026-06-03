"""Tests for create_attempt_chat_impl (formerly attempt_use_previous_internal_impl).

The legacy ``attempt.use_previous`` handler was removed; its "bridge a previous
attempt_chat into the current attempt" behavior was folded into
``app.infra.attempt.chat_create.create_attempt_chat_impl`` via the optional
``previous_attempt_chat_id`` request field.

NOTE: ``module_uses_audit`` is RED on purpose. The audit/emit responsibility that
``use_previous`` used to carry at the infra layer moved OUT of the infra impl
(``create_attempt_chat_impl`` does not audit) and UP into the route wrapper
``app.routes.attempt.chat_create`` (``run_artifact_operation_with_audit``). The
infra-module-level audit behavior this assertion checks no longer exists at the
consolidated infra location; reported rather than guessed/weakened.
"""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_attempt_use_previous_internal_impl_requires_profile_id():
    from app.infra.attempt.chat_create import create_attempt_chat_impl
    with pytest.raises((ValueError, Exception)):
        await create_attempt_chat_impl({})

async def test_attempt_use_previous_internal_impl_is_async():
    from app.infra.attempt.chat_create import create_attempt_chat_impl
    import asyncio
    assert asyncio.iscoroutinefunction(create_attempt_chat_impl)

async def test_attempt_use_previous_internal_impl_module_uses_audit():
    import app.infra.attempt as pkg
    import importlib
    m = importlib.import_module("app.infra.attempt.chat_create")
    source = open(m.__file__).read()
    assert "audit" in source.lower() or "emit" in source.lower()
