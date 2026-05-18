"""Module 09 — Profile seed definitions.

Profiles are bootstrapped using lower-level creates (artifact + resource level)
since _impl functions require a profile_id to already exist. Once the Default
Superadmin is created, all subsequent modules use _impl with SEED_PROFILE_ID.
"""

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Referenced IDs from module 01 resources
# ---------------------------------------------------------------------------

# Roles (from database/seeds/resources/roles.py)
SUPERADMIN_ROLE = sid("role/super-administrator")
ADMIN_ROLE = sid("role/administrator")
INSTRUCTIONAL_ROLE = sid("role/instructional-staff")
MEMBER_GTA_ROLE = sid("role/gta")
MEMBER_UTA_ROLE = sid("role/uta")
GUEST_ROLE = sid("role/guest")

# Flags (from database/seeds/resources/flags.py)
PROFILE_ACTIVE = sid("flag/profile-active")

# Request limits (from database/seeds/resources/request_limits.py)
GUEST_REQUEST_LIMIT = sid("request-limit/daily-10")

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules
# ---------------------------------------------------------------------------

SEED_PROFILE_ID = sid("profile/bootstrap-superadmin")

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
        role_id=SUPERADMIN_ROLE,
        flag_ids=[PROFILE_ACTIVE],
    ),
]
