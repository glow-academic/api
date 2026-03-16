"""Module 09 — Profile seed definitions.

Profiles are bootstrapped using lower-level creates (artifact + resource level)
since _impl functions require a profile_id to already exist. Once the Default
Superadmin is created, all subsequent modules use _impl with SEED_PROFILE_ID.
"""

from uuid import UUID

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

# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

profiles = [
    dict(
        id=SEED_PROFILE_ID,
        name="Default Superadmin",
        role_ids=[SUPERADMIN_ROLE],
        flag_ids=[PROFILE_ACTIVE],
    ),
    dict(
        id=UUID("019b3be4-36ef-7a5f-98ab-ccb879770be0"),
        name="Default Admin",
        role_ids=[ADMIN_ROLE],
        flag_ids=[PROFILE_ACTIVE],
    ),
    dict(
        id=UUID("019b3be4-36f0-785d-9d61-32eae65689ca"),
        name="Default Instructional",
        role_ids=[INSTRUCTIONAL_ROLE],
        flag_ids=[PROFILE_ACTIVE],
    ),
    dict(
        id=UUID("019b3be4-36f0-7eb3-bc4e-bcab772edd92"),
        name="Default Member",
        role_ids=[MEMBER_GTA_ROLE],
        flag_ids=[PROFILE_ACTIVE],
    ),
    dict(
        id=UUID("019b3be4-36f0-792c-82d6-126664ed18b6"),
        name="Default Guest",
        role_ids=[GUEST_ROLE],
        flag_ids=[PROFILE_ACTIVE],
        request_limit_id=GUEST_REQUEST_LIMIT,
    ),
]
