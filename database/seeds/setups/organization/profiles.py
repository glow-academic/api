"""Organization profile updates — link pre-existing profiles to this setup's department."""

from uuid import UUID

from database.seeds.setups.organization.departments import ORGANIZATION_DEPT

# ---------------------------------------------------------------------------
# Pre-existing profile IDs (from 09-profiles in modules 01-10)
# ---------------------------------------------------------------------------

DEFAULT_ADMIN = UUID("019b3be4-36ef-7a5f-98ab-ccb879770be0")
DEFAULT_GUEST = UUID("019b3be4-36f0-792c-82d6-126664ed18b6")
DEFAULT_INSTRUCTIONAL = UUID("019b3be4-36f0-785d-9d61-32eae65689ca")
DEFAULT_MEMBER = UUID("019b3be4-36f0-7eb3-bc4e-bcab772edd92")
DEFAULT_SUPERADMIN = UUID("019b3be4-36f0-788c-9df2-481eb5917940")

# ---------------------------------------------------------------------------
# Profile updates — link pre-existing profiles to this setup's department
# ---------------------------------------------------------------------------

profile_updates = [
    dict(
        profile_id=DEFAULT_ADMIN,
        department_ids=[ORGANIZATION_DEPT],
        email="default-admin@organization.com",
    ),
    dict(
        profile_id=DEFAULT_GUEST,
        department_ids=[ORGANIZATION_DEPT],
        email="default-guest@organization.com",
    ),
    dict(
        profile_id=DEFAULT_INSTRUCTIONAL,
        department_ids=[ORGANIZATION_DEPT],
        email="default-instructional@organization.com",
    ),
    dict(
        profile_id=DEFAULT_MEMBER,
        department_ids=[ORGANIZATION_DEPT],
        email="default-member@organization.com",
    ),
    dict(
        profile_id=DEFAULT_SUPERADMIN,
        department_ids=[ORGANIZATION_DEPT],
        email="default-superadmin@organization.com",
    ),
]
