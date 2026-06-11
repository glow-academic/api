"""Tests for redact_secret_arguments (SEC2 — keep provider keys out of receipts)."""

from app.infra.tools.entries.redact_secrets import (
    _REDACTED,
    redact_secret_arguments,
)


def test_masks_top_level_key():
    out = redact_secret_arguments({"name": "Dr. Smith", "key": "sk-live-abc123"})
    assert out["name"] == "Dr. Smith"
    assert out["key"] == _REDACTED


def test_masks_nested_provider_key():
    """The real leak shape: provider.create arguments nest the key."""
    args = {
        "providers": [
            {"name": "OpenAI", "endpoint": "https://api", "key": "sk-PLAINTEXT"},
            {"name": "Anthropic", "key": "anthropic-PLAINTEXT"},
        ],
        "idempotency_key": "00000000-0000-0000-0000-000000000000",
    }
    out = redact_secret_arguments(args)
    assert out["providers"][0]["key"] == _REDACTED
    assert out["providers"][1]["key"] == _REDACTED
    # Non-secret fields preserved verbatim.
    assert out["providers"][0]["name"] == "OpenAI"
    assert out["providers"][0]["endpoint"] == "https://api"
    # ``idempotency_key`` is NOT a secret value — but it ends in "key" and is a
    # whole-name match? No: only exact field-name matches are masked.
    assert out["idempotency_key"] == "00000000-0000-0000-0000-000000000000"


def test_no_plaintext_secret_survives_anywhere():
    args = {"providers": [{"key": "sk-PLAINTEXT-XYZ"}], "secret": "p@ss"}
    out = redact_secret_arguments(args)
    import json

    blob = json.dumps(out)
    assert "sk-PLAINTEXT-XYZ" not in blob
    assert "p@ss" not in blob


def test_does_not_mutate_input():
    args = {"providers": [{"key": "sk-PLAINTEXT"}]}
    redact_secret_arguments(args)
    # Live arguments (used to actually execute the tool) must be untouched.
    assert args["providers"][0]["key"] == "sk-PLAINTEXT"


def test_preserves_none_secret():
    """An absent optional secret stays None, not a fake redaction marker."""
    out = redact_secret_arguments({"key": None, "name": "x"})
    assert out["key"] is None
    assert out["name"] == "x"


def test_masks_various_secret_names():
    args = {
        "password": "pw",
        "token": "tk",
        "access_token": "at",
        "api_key": "ak",
        "client_secret": "cs",
    }
    out = redact_secret_arguments(args)
    assert all(v == _REDACTED for v in out.values())


def test_non_dict_values_passthrough():
    out = redact_secret_arguments({"count": 3, "tags": ["a", "b"], "flag": True})
    assert out == {"count": 3, "tags": ["a", "b"], "flag": True}
