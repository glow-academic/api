"""Tests for the SSRF endpoint-URL guard (app.utils.url_safety)."""

import pytest

from app.utils.url_safety import validate_endpoint_url


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "https://api.anthropic.com",
        "http://litellm-proxy.example.com:4000",
        "https://my-provider.example.com/v1/",
    ],
)
def test_accepts_legit_public_https_endpoints(url):
    # Should not raise.
    validate_endpoint_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://169.254.169.254",
        "http://localhost:4000/v1",
        "http://127.0.0.1/v1",
        "http://127.0.0.5:8080",
        "https://10.0.0.5/internal",  # private range
        "http://192.168.1.87:8000",  # private range
        "http://172.16.0.1",  # private range
        "http://[::1]/v1",  # ipv6 loopback
        "http://[fd00::1]/v1",  # ipv6 unique-local (private)
        "http://0.0.0.0:5000",  # unspecified
        "file:///etc/passwd",  # non-http scheme
        "gopher://169.254.169.254/",  # non-http scheme
        "http://169.254.169.254.",  # trailing-dot bypass attempt
        "",  # empty
        "https://",  # no host
    ],
)
def test_rejects_internal_metadata_and_bad_scheme(url):
    with pytest.raises(ValueError):
        validate_endpoint_url(url)
