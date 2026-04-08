"""Fresh profile seed definitions — setup-specific, independent from base modules.

Creates setup-specific versions of the default profiles with emails.
These are separate artifacts from the bootstrap profile (SEED_PROFILE_ID)
which exists only to run seed operations.
"""

from database.seeds.ids import sid
from database.seeds.profiles import (
    ADMIN_ROLE,
    GUEST_ROLE,
    GUEST_REQUEST_LIMIT,
    INSTRUCTIONAL_ROLE,
    MEMBER_GTA_ROLE,
    PROFILE_ACTIVE,
    SUPERADMIN_ROLE,
)

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

FRESH_SUPERADMIN = sid("fresh/profile/superadmin")
FRESH_SUPERADMIN_RESOURCE = sid("fresh/profile-resource/superadmin")
FRESH_ADMIN = sid("fresh/profile/admin")
FRESH_ADMIN_RESOURCE = sid("fresh/profile-resource/admin")
FRESH_INSTRUCTIONAL = sid("fresh/profile/instructional")
FRESH_INSTRUCTIONAL_RESOURCE = sid("fresh/profile-resource/instructional")
FRESH_MEMBER = sid("fresh/profile/member")
FRESH_MEMBER_RESOURCE = sid("fresh/profile-resource/member")
FRESH_GUEST = sid("fresh/profile/guest")
FRESH_GUEST_RESOURCE = sid("fresh/profile-resource/guest")

# ---------------------------------------------------------------------------
# Setup-specific profiles
# ---------------------------------------------------------------------------

setup_profiles = [
    # Note: superadmin is bootstrapped by the runner, not created here.
    # It gets email via the bootstrap process.
    dict(
        id=FRESH_ADMIN,
        resource_id=FRESH_ADMIN_RESOURCE,
        name="Default Admin",
        email="admin@glow.local",
        role_ids=[ADMIN_ROLE],
        flag_id=PROFILE_ACTIVE,
    ),
    dict(
        id=FRESH_INSTRUCTIONAL,
        resource_id=FRESH_INSTRUCTIONAL_RESOURCE,
        name="Default Instructional",
        email="instructional@glow.local",
        role_ids=[INSTRUCTIONAL_ROLE],
        flag_id=PROFILE_ACTIVE,
    ),
    dict(
        id=FRESH_MEMBER,
        resource_id=FRESH_MEMBER_RESOURCE,
        name="Default Member",
        email="member@glow.local",
        role_ids=[MEMBER_GTA_ROLE],
        flag_id=PROFILE_ACTIVE,
    ),
    dict(
        id=FRESH_GUEST,
        resource_id=FRESH_GUEST_RESOURCE,
        name="Default Guest",
        email="guest@glow.local",
        role_ids=[GUEST_ROLE],
        flag_id=PROFILE_ACTIVE,
        request_limit_id=GUEST_REQUEST_LIMIT,
    ),
]
