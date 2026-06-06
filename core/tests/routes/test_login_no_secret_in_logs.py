"""Secrets-in-logs guard: the OAuth ``/callback`` handler must not log the raw
token-endpoint response body.

``routes/login.py`` exchanges the authorization code at Keycloak's token
endpoint. On a non-200 it previously did::

    logger.error(f"Token exchange failed: {resp.status_code} {resp.text}")

i.e. it echoed the *raw upstream body* of the most secret-bearing endpoint in
the system into an ERROR log (always enabled in prod). This is the
response-exposure-in-logs class (companion to #264): a token-endpoint body can
carry sensitive material, and ERROR logs are shipped/persisted.

This test drives the *real* ``callback`` handler with a stubbed
``httpx.AsyncClient`` that returns a non-200 whose body contains a fake secret,
captures the emitted log records via ``caplog``, and asserts the secret body is
never present in any record — only the non-secret OIDC ``error`` code is.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest
from fastapi import HTTPException

import app.routes.login as login


_FAKE_SECRET_BODY = (
    '{"error":"invalid_grant","access_token":"SUPERSECRET-leaked-token-12345",'
    '"client_secret":"cs-DO-NOT-LOG-9999"}'
)


class _FakeResp:
    status_code = 400

    @property
    def text(self) -> str:
        return _FAKE_SECRET_BODY

    def json(self) -> dict:
        return {
            "error": "invalid_grant",
            "access_token": "SUPERSECRET-leaked-token-12345",
            "client_secret": "cs-DO-NOT-LOG-9999",
        }


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, *args, **kwargs):
        return _FakeResp()


def test_callback_failure_does_not_log_token_endpoint_body(monkeypatch, caplog):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    with caplog.at_level(logging.DEBUG, logger=login.logger.name):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(login.callback(code="any-code"))

    assert ei.value.status_code == 400

    blob = "\n".join(r.getMessage() for r in caplog.records)
    # The raw secret-bearing body must never reach the logs.
    assert "SUPERSECRET-leaked-token-12345" not in blob
    assert "cs-DO-NOT-LOG-9999" not in blob
    assert _FAKE_SECRET_BODY not in blob
    # But the non-secret OIDC error code should still be surfaced for debugging.
    assert "invalid_grant" in blob
    assert "status=400" in blob
