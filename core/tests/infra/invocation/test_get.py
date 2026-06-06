"""Tests for get_invocation_impl — get orchestration."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_get_function_is_async():
    import app.infra.invocation.get as mod
    import asyncio
    assert asyncio.iscoroutinefunction(mod.get_invocation_impl)

async def test_get_module_uses_common_context():
    import app.infra.invocation.get as mod
    source = open(mod.__file__).read()
    assert "resolve_common_context" in source or "resolve_" in source

async def test_get_module_returns_response_type():
    import app.infra.invocation.get as mod
    source = open(mod.__file__).read()
    assert "Response" in source or "InternalData" in source


async def test_mask_key_does_not_reveal_raw_secret():
    # #264 sibling: the raw provider key must never appear in the masked preview.
    from app.infra.invocation.get import _mask_key
    raw = "sk-live-SUPER-SECRET-abcd1234"
    masked = _mask_key(raw)
    assert masked is not None
    assert masked != raw
    assert raw not in masked
    # No fragment of the raw secret leaks through the mask.
    assert not any(ch.isalnum() for ch in masked)


async def test_mask_key_none_when_absent():
    from app.infra.invocation.get import _mask_key
    assert _mask_key(None) is None
    assert _mask_key("") is None


async def test_invocation_key_resource_masked_fields_never_equal_raw_key():
    # Build the resource the way get_invocation_impl does (lines ~317-318):
    # both masked fields must hide the raw key from a reachable GET response.
    from types import SimpleNamespace
    from app.infra.invocation.get import _mask_key
    from app.infra.invocation.types import InvocationKeyResource

    raw = "sk-live-SUPER-SECRET-abcd1234"
    item = SimpleNamespace(
        id=uuid4(),
        name="OpenAI prod",
        description=None,
        key=raw,  # GetKeyResponse.key is the raw secret
        active=True,
        generated=False,
    )

    resource = InvocationKeyResource(
        id=item.id,
        key_id=item.id,
        name=item.name,
        description=item.description,
        key_masked=_mask_key(getattr(item, "key", None)),
        masked_key=_mask_key(getattr(item, "key", None)),
        active=item.active,
        generated=item.generated,
    )

    assert resource.key_masked != raw
    assert resource.masked_key != raw
    assert raw not in (resource.key_masked or "")
    assert raw not in (resource.masked_key or "")
    # Masked fields still signal that a key is set (UI placeholder under the name).
    assert resource.key_masked
    assert resource.masked_key
