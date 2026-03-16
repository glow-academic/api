"""Organization setting seed definitions.

References pre-existing auth, system, and threshold resources from modules 01-10.
Provider keys and auth item keys are created by the keys module and linked here.
"""

from uuid import UUID

from database.seeds.auths import GOOGLE_AUTH
from database.seeds.ids import sid
from database.seeds.setups.organization.departments import ORGANIZATION_DEPT
from database.seeds.setups.organization.keys import AUTH_ITEM_KEY_IDS, PROVIDER_KEY_IDS

# ---------------------------------------------------------------------------
# Pre-existing threshold resource IDs (from 01-resources/06-thresholds.sql)
# ---------------------------------------------------------------------------

THRESHOLD_SUCCESS = UUID("019b995b-5308-7a8e-9d31-b08127742439")  # 85
THRESHOLD_WARNING = UUID("019b995b-5309-714f-a5f6-5614613257b1")  # 80
THRESHOLD_DANGER = UUID("019b995b-5309-74df-991a-c28980b294f2")  # 70

# ---------------------------------------------------------------------------
# Pre-existing flag IDs (from 01-resources/)
# ---------------------------------------------------------------------------

FLAG_ACTIVE = UUID("019be334-bfc6-717e-9377-b63fc43ae0c6")
FLAG_PRACTICE = UUID("019b995a-86ef-78fc-adec-fc4db3a87c0d")
FLAG_SCORING = UUID("019bcc4d-d9c6-7a09-b99a-919d8f85cab1")

# ---------------------------------------------------------------------------
# Pre-existing system resource IDs (from 10-systems/)
# ---------------------------------------------------------------------------

SYSTEMS = [
    UUID("019caf25-99c7-78a6-849d-1258f99e47e4"),  # Activity
    UUID("019caf25-99c8-7bba-946c-e6b9d55d2fc3"),  # Agent
    UUID("019caf25-99ca-7f95-9038-206fe1734be3"),  # Attempt Chat
    UUID("019caf25-99cb-700e-b879-41628a9218c5"),  # Attempt Grade
    UUID("019caf25-99cc-7cc3-a040-981957508b2a"),  # Attempt Insight
    UUID("019caf25-99cd-7470-bc4b-7eb189b96d43"),  # Auth
    UUID("019caf25-99cf-7087-81ee-58450c4a9aca"),  # Benchmark
    UUID("019caf25-99d0-7d2c-bfba-49be9f4acd87"),  # Chat
    UUID("019caf25-99d1-771d-a01f-80f8aae924df"),  # Cohort
    UUID("019caf25-99d2-752b-ab22-5f9455aa1e9a"),  # Dashboard
    UUID("019caf25-99d4-7fb7-8cec-e9a0de527479"),  # Department
    UUID("019caf25-99d5-7ff1-a78c-485cbcd14b60"),  # Document
    UUID("019caf25-99d6-70d6-90eb-f580991fcf89"),  # Eval
    UUID("019caf25-99d7-792a-a47b-246dd0a84352"),  # Field
    UUID("019caf25-99d9-73dc-a8be-a47def47c3e0"),  # Group
    UUID("019caf25-99da-7af2-875a-9c8eb8fd70e9"),  # Health
    UUID("019caf25-99db-7090-87a2-0c2dff148860"),  # Home
    UUID("019caf25-99dc-73fa-848e-fcc5947b6bb1"),  # Invocation
    UUID("019caf25-99de-7c11-9dd7-a8878ef28a07"),  # Leaderboard
    UUID("019caf25-99df-716b-abc9-a4c3ba2f32c8"),  # Model
    UUID("019caf25-99e0-7e2c-9f64-37bde94a00c6"),  # Parameter
    UUID("019caf25-99e1-717c-b4ea-8a6055664887"),  # Persona
    UUID("019caf25-99e3-723d-920c-78e5ac8f19dd"),  # Practice
    UUID("019caf25-99e4-7571-8bb7-155d53173005"),  # Pricing
    UUID("019caf25-99e5-75e8-b0f1-a5bd20b35bfa"),  # Profile
    UUID("019caf25-99e6-7886-96fe-71a0bb6090d1"),  # Provider
    UUID("019caf25-99e8-7cd5-8d61-a7800f1a6686"),  # Record
    UUID("019caf25-99e9-72be-8c27-e3f264eeefa4"),  # Reports
    UUID("019caf25-99ea-7f17-8bac-4ed76165c512"),  # Rubric
    UUID("019caf25-99ec-727f-be3c-4224ee4f9bef"),  # Scenario
    UUID("019caf25-99ed-79c0-926c-d302897f4322"),  # Session
    UUID("019caf25-99ee-7f5e-934d-1c9eaeb52f24"),  # Setting
    UUID("019caf25-99ef-7358-87a9-29cb15f52fd3"),  # Simulation
    UUID("019caf25-99f1-7230-bee2-f5e15bd56400"),  # Test Insight
    UUID("019caf25-99f2-7ea3-8a59-24fcd0ff8b8c"),  # Test Grade
    UUID("019caf25-99f3-7408-b7d0-968fe57800f7"),  # Tool
]

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

ORGANIZATION_SETTING = sid("org/setting/organization")

# ---------------------------------------------------------------------------
# Setting definitions
# ---------------------------------------------------------------------------

settings = [
    dict(
        id=ORGANIZATION_SETTING,
        name="Organization Settings",
        description="Settings for the Organization department",
        active_flag=True,
        department_ids=[ORGANIZATION_DEPT],
        auth_ids=[GOOGLE_AUTH],
        provider_key_ids=PROVIDER_KEY_IDS,
        auth_item_key_ids=AUTH_ITEM_KEY_IDS,
        system_ids=SYSTEMS,
        threshold_ids=[THRESHOLD_SUCCESS, THRESHOLD_WARNING, THRESHOLD_DANGER],
    ),
]
