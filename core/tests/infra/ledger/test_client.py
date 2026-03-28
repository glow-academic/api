"""Tests for ledger client — phone_home HTTP call."""

import pytest

from app.infra.ledger.client import (
    DEFAULT_LEARNLOOP_URL,
    PHONE_HOME_TIMEOUT,
    _deployment_token,
    _learnloop_url,
)

pytestmark = pytest.mark.asyncio


async def test_learnloop_url_default(monkeypatch):
    monkeypatch.delenv("LEARNLOOP_API_URL", raising=False)
    assert _learnloop_url() == DEFAULT_LEARNLOOP_URL


async def test_learnloop_url_custom(monkeypatch):
    monkeypatch.setenv("LEARNLOOP_API_URL", "https://custom.example.com/")
    assert _learnloop_url() == "https://custom.example.com"  # trailing slash stripped


async def test_deployment_token_raises_when_empty(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_TOKEN", "")
    with pytest.raises(RuntimeError, match="DEPLOYMENT_TOKEN"):
        _deployment_token()


async def test_deployment_token_returns_env_value(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_TOKEN", "my-test-token")
    assert _deployment_token() == "my-test-token"


async def test_phone_home_timeout_value():
    assert PHONE_HOME_TIMEOUT == 10


async def test_phone_home_posts_to_correct_url(monkeypatch):
    """Verify phone_home constructs the right URL and returns a checkpoint."""
    import httpx

    from app.infra.ledger.client import phone_home

    monkeypatch.setenv("DEPLOYMENT_TOKEN", "tok-123")
    monkeypatch.setenv("LEARNLOOP_API_URL", "https://test-api.example.com")

    captured_requests = []

    async def mock_post(self, url, json=None, headers=None):
        captured_requests.append({"url": url, "json": json, "headers": headers})

        class MockResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self_inner):
                return {
                    "authorized": True,
                    "num_left": 100,
                    "num_to_next_check": 5,
                }

        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await phone_home(
        current_sequence=10,
        current_hash="abc123",
        attempts_since_last_check=3,
    )

    assert result.authorized is True
    assert result.num_left == 100
    assert result.num_to_next_check == 5
    assert len(captured_requests) == 1
    assert captured_requests[0]["url"] == "https://test-api.example.com/provision/usage/check"
    assert captured_requests[0]["json"]["current_sequence"] == 10
    assert "Bearer tok-123" in captured_requests[0]["headers"]["Authorization"]
