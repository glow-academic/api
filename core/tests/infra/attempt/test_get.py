"""Tests for get_attempt_impl — get orchestration."""
from unittest.mock import AsyncMock
from uuid import UUID, uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_get_function_is_async():
    import app.infra.attempt.get as mod
    import asyncio
    assert asyncio.iscoroutinefunction(mod.get_attempt_impl)


# ---------------------------------------------------------------------------
# Regression: agent-run "Attempt Get" tool invocation must not TypeError when
# the model omits the (schema-required) ``attempt_id``.
#
# Live repro (attempts-stop cli tape): the agent ran under
# ``tool_choice=required`` and called "Attempt Get" without ``attempt_id``.
# The dispatch path (``execute_infra_operation`` kwargs branch) renders the
# tool's ``args_outputs`` to ``{"attempt_id": ""}``, then ``sanitize_model_kwargs``
# strips the empty string — so ``get_attempt_impl`` was invoked with NO
# ``attempt_id`` at all. With a required keyword-only param that raised
# ``get_attempt_impl() missing 1 required keyword-only argument: 'attempt_id'``
# (error_type TypeError) and failed the whole run. Every sibling ``*_Get`` impl
# already declares ``<entity>_id: UUID | None = None`` and degrades gracefully;
# this asserts get_attempt_impl now does too.
# ---------------------------------------------------------------------------


def _attempt_get_tool_def() -> dict:
    """The enriched "Attempt Get" tool_def as prepare_pipeline produces it.

    Mirrors database/seeds/tools.py ("Attempt Get",
    args_outputs=["artifact_attempt", "operation_get", "attempt_id"]) +
    the args_outputs seed templates.
    """
    return {
        "name": "Attempt Get",
        "_args_outputs": [
            {"name": "artifact", "template": "attempt"},
            {"name": "operation", "template": "get"},
            {"name": "attempt_id", "template": "{{ attempt_id }}"},
        ],
        "_permissions": [{"artifact": "attempt", "operation": "get"}],
    }


def _dispatch_kwargs_for_attempt_get(llm_inputs: dict) -> dict:
    """Reproduce execute_infra_operation's kwargs-path arg resolution.

    render_output_map -> sanitize_model_kwargs -> _coerce_kwargs_to_signature,
    exactly the chain the agent-run loop runs before calling the impl.
    """
    from app.infra.attempt.get import get_attempt_impl
    from app.infra.tools.execute_infra_operation import (
        _coerce_kwargs_to_signature,
        render_output_map,
    )
    from app.infra.tools.resolve_tool_spec import resolve_tool_spec
    from app.infra.tools.sanitize import sanitize_model_kwargs

    spec = resolve_tool_spec(_attempt_get_tool_def(), llm_inputs)
    # Single attempt-get target resolved from the tool's permissions.
    assert [(t.artifact, t.operation) for t in spec.targets] == [("attempt", "get")]
    rendered = render_output_map(spec.inputs, spec.output_map)
    kwargs = sanitize_model_kwargs(rendered)
    return _coerce_kwargs_to_signature(get_attempt_impl, kwargs)


async def test_agent_run_attempt_get_missing_id_is_graceful_not_typeerror():
    """Model omits attempt_id -> impl returns canonical 'no attempt', no TypeError."""
    from app.infra.attempt.get import get_attempt_impl
    from app.infra.attempt.types import GetAttemptDetailResponse

    # The model called the tool with no attempt_id (forced tool call).
    kwargs = _dispatch_kwargs_for_attempt_get({})
    assert "attempt_id" not in kwargs  # empty render was stripped by sanitize

    # pool/redis are pass-throughs (deps-as-params); the missing-id guard
    # returns before either is touched, so sentinels are fine.
    resp = await get_attempt_impl(
        object(), object(), profile_id=uuid4(), **kwargs,
    )
    assert isinstance(resp, GetAttemptDetailResponse)
    assert resp.attempt_exists is False
    assert resp.access_denied is False


async def test_agent_run_attempt_get_forwards_attempt_id(monkeypatch):
    """Model supplies attempt_id -> it reaches get_attempt_internal as a UUID."""
    import app.infra.attempt.get as mod
    from app.infra.attempt.types import GetAttemptDetailResponse

    attempt_id = uuid4()
    kwargs = _dispatch_kwargs_for_attempt_get({"attempt_id": str(attempt_id)})
    # Jinja renders a string; the dispatch coerces it back to the impl's
    # declared UUID type before the call.
    assert kwargs["attempt_id"] == attempt_id
    assert isinstance(kwargs["attempt_id"], UUID)

    internal = AsyncMock(return_value=type(
        "Data", (), {"attempt_exists": False, "access_denied": True, "actor_name": "x"},
    )())
    monkeypatch.setattr(mod, "get_attempt_internal", internal)

    resp = await mod.get_attempt_impl(
        object(), object(), profile_id=uuid4(), bypass_cache=True, **kwargs,
    )
    assert isinstance(resp, GetAttemptDetailResponse)
    internal.assert_awaited_once()
    assert internal.await_args.kwargs["attempt_id"] == attempt_id

async def test_get_module_uses_common_context():
    import app.infra.attempt.get as mod
    source = open(mod.__file__).read()
    assert "resolve_common_context" in source or "resolve_" in source

async def test_get_module_returns_response_type():
    import app.infra.attempt.get as mod
    source = open(mod.__file__).read()
    assert "Response" in source or "InternalData" in source


def test_image_entry_retains_upload_id():
    """Regression: ImageEntry must expose upload_id.

    get_attempt_internal fetches ``entry.upload_id`` into resource_meta and
    passes ``upload_id=...`` into ImageEntry. The model previously lacked the
    field, so pydantic (extra=ignore) silently dropped it and the upload_id
    never reached the API response. This asserts the value survives.
    """
    from app.infra.attempt.types import ImageEntry

    up = uuid4()
    entry = ImageEntry(image_id=uuid4(), upload_id=up, name="img", description="d")
    assert entry.upload_id == up
    assert "upload_id" in ImageEntry.model_fields


def test_video_entry_retains_upload_id():
    """Regression: VideoEntry must expose upload_id (see ImageEntry above)."""
    from app.infra.attempt.types import VideoEntry

    up = uuid4()
    entry = VideoEntry(video_id=uuid4(), upload_id=up, name="vid", description="d")
    assert entry.upload_id == up
    assert "upload_id" in VideoEntry.model_fields
