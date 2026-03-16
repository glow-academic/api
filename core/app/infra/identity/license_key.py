"""License key validation — calls external billing service.

Stub: always returns valid. In production, this would call an external
billing API to validate the key and return org/plan info.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LicenseInfo:
    """Result of license key validation."""

    valid: bool
    org_id: str | None = None
    plan: str | None = None
    error: str | None = None


async def validate_license_key(key: str) -> LicenseInfo:
    """Validate a license key against the external billing service.

    Stub: always returns valid.
    Production: POST https://billing.example.com/v1/keys/validate

    Args:
        key: The license key string (e.g. "glw_sk_abc123")

    Returns:
        LicenseInfo with validation result
    """
    if not key:
        return LicenseInfo(valid=False, error="Missing license key")

    # TODO: Call external billing API
    # response = await httpx.post("https://billing.example.com/v1/keys/validate", json={"key": key})
    # return LicenseInfo(valid=response.json()["valid"], org_id=response.json()["org_id"], ...)

    return LicenseInfo(valid=True, org_id="dev", plan="dev")
