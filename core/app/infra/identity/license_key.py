"""License key validation — local string match against LICENSE_KEY env var.

In production, LICENSE_KEY is injected during provisioning. The client sends
the same key via X-Api-Key header. Simple equality check.

Dev mode: if LICENSE_KEY is not set, any non-empty key is accepted.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LicenseInfo:
    """Result of license key validation."""

    valid: bool
    org_id: str | None = None
    plan: str | None = None
    error: str | None = None


async def validate_license_key(key: str) -> LicenseInfo:
    """Validate a license key against the local LICENSE_KEY env var.

    - If LICENSE_KEY is not set: dev mode, any non-empty key is accepted.
    - If LICENSE_KEY is set: exact string match required.
    """
    if not key:
        return LicenseInfo(valid=False, error="Missing license key")

    license_key = os.getenv("LICENSE_KEY")

    if not license_key:
        # Dev mode — no LICENSE_KEY configured, accept any key
        return LicenseInfo(valid=True, org_id="dev", plan="dev")

    if key != license_key:
        return LicenseInfo(valid=False, error="Invalid license key")

    return LicenseInfo(valid=True)
