"""Module 09 — Profile seed definitions.

Profiles are bootstrapped using lower-level creates (artifact + resource level)
since _impl functions require a profile_id to already exist. Once the Default
Superadmin is created, all subsequent modules use _impl with SEED_PROFILE_ID.
"""

from uuid import UUID

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Referenced IDs from module 01 resources
# ---------------------------------------------------------------------------

# Roles (from database/seeds/resources/roles.py)
SUPERADMIN_ROLE = UUID("019bbabc-5a3b-7481-bbf5-a7c2193bc5e4")
ADMIN_ROLE = UUID("019bbabc-5a36-76d3-8fc3-8415fe308cd3")
INSTRUCTIONAL_ROLE = UUID("019bbabc-5a3b-741e-bad3-474cc6c05fd6")
MEMBER_GTA_ROLE = UUID("019bf21d-4d50-74fc-8c81-be446d602de2")
GUEST_ROLE = UUID("019bbabc-5a37-7028-8b98-728b7aa54d0d")

# Flags (from database/seeds/resources/flags.py)
PROFILE_ACTIVE = UUID("019be334-bfc5-7197-8f3e-c203790334de")

# Request limits (from database/seeds/resources/request_limits.py)
GUEST_REQUEST_LIMIT = UUID("019bb553-e77f-797c-ae44-544fbe10351b")

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules
# ---------------------------------------------------------------------------

SEED_PROFILE_ID = UUID("019b3be4-36f0-788c-9df2-481eb5917940")

# Deterministic resource ID for the bootstrap profile
SEED_PROFILE_RESOURCE = sid("default/profile-resource/superadmin")

# ---------------------------------------------------------------------------
# Bootstrap profile — minimal, only needed for SEED_PROFILE_ID to run seed operations.
# Setup-specific profiles (with emails, departments) are in each setup folder.
# ---------------------------------------------------------------------------

profiles = [
    dict(
        id=SEED_PROFILE_ID,
        resource_id=SEED_PROFILE_RESOURCE,
        name="Bootstrap Superadmin",
        role_ids=[SUPERADMIN_ROLE],
        flag_ids=[PROFILE_ACTIVE],
    ),
]
