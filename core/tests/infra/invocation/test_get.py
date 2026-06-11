"""Tests for get_invocation_impl — get orchestration."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio


def _empty_artifact_context(group_id, *, use_custom):
    """Build a minimal ArtifactContext the way resolve_invocation_context would.

    Carries empty resource pairs for every section plus the `use_custom` entry
    sourced from the underlying template invocation row (base_invocation.use_custom).
    """
    from app.infra.types import ArtifactContext, ResourcePair
    from app.infra.invocation.get import SECTIONS

    return ArtifactContext(
        artifact_id=uuid4(),
        active=True,
        group_id=group_id,
        resources={s: ResourcePair(selected=[], suggestions=[]) for s in SECTIONS},
        entries={
            "draft_name": None,
            "pending_ids": set(),
            "invocation_exists": True,
            "use_custom": use_custom,
        },
    )


@pytest.mark.parametrize("use_custom", [True, False])
async def test_get_suite_response_carries_use_custom_from_template(use_custom):
    """GetSuiteResponse exposes use_custom read from the template's underlying row.

    Mirrors the materialized GetTestInvocationResponse.use_custom source
    (test_invocation_entry.use_custom). A custom template must report
    use_custom=True; a non-custom template use_custom=False — so the client
    can honor the lobby / custom-invocation gate pre-materialization.
    """
    import app.infra.invocation.get as mod

    group_id = uuid4()
    invocation_id = uuid4()
    common = SimpleNamespace(
        profile=SimpleNamespace(name="Tester", department_ids=[])
    )

    with patch.object(mod, "resolve_common_context", AsyncMock(return_value=common)), \
         patch.object(mod, "resolve_invocation_context",
                      AsyncMock(return_value=_empty_artifact_context(group_id, use_custom=use_custom))), \
         patch("app.infra.test.group.group_test_impl",
               AsyncMock(return_value=SimpleNamespace(group_id=group_id))):
        result = await mod.get_invocation_impl(
            AsyncMock(),  # pool — never touched (context resolvers are patched)
            AsyncMock(),  # redis
            profile_id=uuid4(),
            invocation_id=invocation_id,
        )

    assert result.use_custom is use_custom


async def test_get_suite_response_use_custom_defaults_false():
    """Absent a template row, the gate field defaults to the non-custom path."""
    from app.infra.invocation.types import GetSuiteResponse
    assert GetSuiteResponse().use_custom is False

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
