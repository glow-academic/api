"""SSRF guard for user/admin-supplied outbound URLs.

Provider ``endpoint`` / ``base_url`` values are stored in
``endpoints_resource`` and later used verbatim as the litellm/OpenAI
``base_url`` (``api_base``) for *server-side* outbound LLM calls. Any
authenticated caller can set this value (provider create/draft), so an
unvalidated URL lets a caller make the server reach cloud-metadata
(``169.254.169.254``), loopback, or private-range hosts — a classic SSRF.

``validate_endpoint_url`` rejects non-http(s) schemes and obvious
internal/metadata targets. It is intentionally minimal (no DNS
resolution / rebinding defence — out of scope) and raises ``ValueError``
so existing route error handlers surface it as HTTP 400.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}

# Hostnames that always resolve to a local/internal target.
_BLOCKED_HOSTNAMES = {
    "localhost",
    "ip6-localhost",
    "ip6-loopback",
}


def _is_blocked_ip(host: str) -> bool:
    """True if ``host`` is an IP literal in a non-routable / internal range."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local  # 169.254.0.0/16 + fe80::/10 (cloud metadata)
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_endpoint_url(url: str) -> None:
    """Reject endpoint URLs that point at internal/metadata targets.

    Raises ``ValueError`` for an unsafe URL; returns ``None`` if the URL
    is an acceptable public http(s) endpoint.
    """
    if not url or not url.strip():
        raise ValueError("Endpoint URL must not be empty")

    parsed = urlparse(url.strip())

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"Endpoint URL scheme '{parsed.scheme}' is not allowed; "
            "only http and https are permitted"
        )

    host = (parsed.hostname or "").strip().rstrip(".").lower()
    if not host:
        raise ValueError("Endpoint URL must include a host")

    if host in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Endpoint URL host '{host}' is not allowed (internal target)")

    if _is_blocked_ip(host):
        raise ValueError(
            f"Endpoint URL host '{host}' is not allowed (internal/metadata target)"
        )
