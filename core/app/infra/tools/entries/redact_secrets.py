"""Redact secret fields out of an audited tool-call arguments payload.

The audit chain persists a tool call's ``arguments`` verbatim into a
downloadable ``.txt`` upload and ``.json`` call receipt
(``create_tool_call._persist_audit_writes``). Some operations carry a
provider/auth *secret* in those arguments — most notably the plaintext
provider API key (``CreateProviderItem.key``) on ``provider.create``.
Persisting that secret to a downloadable receipt is a secret-at-rest leak
(SEC2): anyone who can reach the call-download route can read the raw key.

This helper masks known secret field names (recursively, so the nested
``providers[].key`` / ``auths[].key`` shapes are covered) before the
arguments are written to the receipt. It returns a *copy* — the live
``arguments`` dict used to execute the tool is never mutated, only the
audit artifact is sanitized.
"""

from __future__ import annotations

from typing import Any

# Field names whose values are secrets and must never be persisted into a
# downloadable audit receipt. Matched case-insensitively against dict keys
# at every nesting level. ``key``/``keys`` cover the provider/auth raw API
# key; the rest are defensive coverage for any future secret-bearing arg.
_SECRET_KEYS: frozenset[str] = frozenset(
    {
        "key",
        "keys",
        "secret",
        "secrets",
        "password",
        "passwd",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "private_key",
        "client_secret",
        "credential",
        "credentials",
    }
)

_REDACTED = "***REDACTED***"


def _redact(value: object) -> object:
    """Recursively redact secret-named fields inside ``value``."""
    if isinstance(value, dict):
        out: dict[object, object] = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in _SECRET_KEYS:
                # Preserve None (an absent optional secret stays absent) so a
                # redacted receipt can't be mistaken for "a secret was set"
                # when it wasn't. A present secret of any shape → mask string.
                out[k] = None if v is None else _REDACTED
            else:
                out[k] = _redact(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


def redact_secret_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of ``arguments`` with secret fields masked.

    Pure function — never mutates the input. Used by the audit-persist
    path so the persisted ``.txt``/``.json`` receipt carries a masked key
    instead of the plaintext secret.
    """
    # ``_redact`` always returns a dict for a dict input.
    redacted = _redact(arguments)
    assert isinstance(redacted, dict)
    return redacted
