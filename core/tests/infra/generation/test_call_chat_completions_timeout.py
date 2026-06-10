"""Upstream timeout parity for the chat-completions fallback path.

The Responses API call (`_call_responses_api`) pins ``timeout=120.0``. The
chat-completions fallback (`_call_chat_completions_api`) must pass the same
cap so a stalled DGX on the fallback path cannot tie up a worker for
litellm's ~600s default.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infra.generation import execute as execute_mod
from app.infra.generation.execute import (
    _call_chat_completions_api,
    _call_responses_api,
)

pytestmark = pytest.mark.asyncio


async def test_chat_completions_passes_120s_timeout():
    """The chat-completions call is invoked with timeout=120.0."""
    with patch.object(execute_mod, "litellm", create=True) as litellm_mock:
        litellm_mock.acompletion = AsyncMock(return_value="ok")
        await _call_chat_completions_api(
            model="local-text",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            tool_choice="auto",
            api_key=None,
            base_url=None,
            temperature=0.0,
            reasoning=None,
            extra_body=None,
        )

    litellm_mock.acompletion.assert_awaited_once()
    kwargs = litellm_mock.acompletion.await_args.kwargs
    assert kwargs["timeout"] == 120.0


async def test_chat_and_responses_timeouts_match():
    """Both upstream paths use the same timeout value (parity)."""
    with patch.object(execute_mod, "litellm", create=True) as litellm_mock:
        litellm_mock.model_cost = {}
        litellm_mock.acompletion = AsyncMock(return_value="ok")
        litellm_mock.aresponses = AsyncMock(return_value="ok")

        await _call_chat_completions_api(
            model="local-text",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            tool_choice="auto",
            api_key=None,
            base_url=None,
            temperature=0.0,
            reasoning=None,
            extra_body=None,
        )
        await _call_responses_api(
            model="local-text",
            responses_input=[{"role": "user", "content": "hi"}],
            tools=None,
            tool_choice="auto",
            api_key=None,
            base_url=None,
            temperature=0.0,
            extra_body=None,
        )

    chat_timeout = litellm_mock.acompletion.await_args.kwargs["timeout"]
    responses_timeout = litellm_mock.aresponses.await_args.kwargs["timeout"]
    assert chat_timeout == responses_timeout == 120.0
