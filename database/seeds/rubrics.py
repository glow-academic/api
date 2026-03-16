"""Rubric module seeds.

21 base rubrics (one per artifact type). All share the same 5 standard groups,
25 standards, 3 points, and 2 flags — only differ in name, description, and IDs.
"""

from uuid import UUID

# Shared across all 21 rubrics
_POINT_IDS = [
    UUID("019b995b-52ec-7b7b-baf4-2c7b3162100b"),
    UUID("019b995b-52ec-7b7e-9cc6-35aae7c0fe5f"),
    UUID("019b995b-52ed-7233-bdaf-88cbcc29083e"),
]

_STANDARD_GROUP_IDS = [
    UUID("019b3be4-3cc0-71ef-a1d4-b3d0deac7ead"),
    UUID("019b3be4-3cc0-72ae-8181-dc2d5f6cee0d"),
    UUID("019b3be4-3cc0-72bb-aef9-c6d1c0a794d5"),
    UUID("019b3be4-3cc0-72c6-8b83-ba801e217cbf"),
    UUID("019b3be4-3cc0-72d3-9909-6eaf43e3d094"),
]

_STANDARD_IDS = [
    UUID("019b3be4-3ccb-708d-80e7-51b691b555a7"),
    UUID("019b3be4-3ccb-79f6-94ba-79f5d64f4da5"),
    UUID("019b3be4-3ccb-7a0a-aa26-89b6b78b15c8"),
    UUID("019b3be4-3ccb-7a13-b68a-7356120e342d"),
    UUID("019b3be4-3ccb-7c83-bf5d-78130778498f"),
    UUID("019b3be4-3ccb-7c8d-9223-a4036e26ca5c"),
    UUID("019b3be4-3ccb-7c9a-a648-3653254dd832"),
    UUID("019b3be4-3ccb-7ca6-9eae-11efeb2889ef"),
    UUID("019b3be4-3ccb-7cb6-9c52-3c1a6049430f"),
    UUID("019b3be4-3ccb-7cc1-ac03-582413caba8c"),
    UUID("019b3be4-3ccb-7ccd-b136-489245b9d44e"),
    UUID("019b3be4-3ccb-7cdd-8d41-28b981adbb2b"),
    UUID("019b3be4-3ccb-7ceb-86fc-0faa43b38349"),
    UUID("019b3be4-3ccb-7cf4-bdf1-adc4bbac9025"),
    UUID("019b3be4-3ccb-7cfe-91dc-4c083ceb6478"),
    UUID("019b3be4-3ccb-7d07-bc1f-8bbc88df7d59"),
    UUID("019b3be4-3ccb-7d11-b870-8930594fec0d"),
    UUID("019b3be4-3ccb-7d18-a14f-f68e642a3cfd"),
    UUID("019b3be4-3ccb-7d21-9879-c7f0a428f46d"),
    UUID("019b3be4-3ccb-7d2b-a60d-6347af838659"),
    UUID("019b3be4-3ccb-7d32-ab5d-00b1134aa994"),
    UUID("019b3be4-3ccb-7d3b-97df-8c24df676cf2"),
    UUID("019b3be4-3ccc-73e6-9e54-e88b8c142cb2"),
    UUID("019b3be4-3ccc-73f7-965d-791773e2baba"),
    UUID("019b3be4-3ccc-7402-a396-24de5a95f832"),
]


def _rubric(id: str, name: str, description: str) -> dict:
    return dict(
        id=UUID(id),
        name=name,
        description=description,
        point_ids=_POINT_IDS,
        standard_group_ids=_STANDARD_GROUP_IDS,
        standard_ids=_STANDARD_IDS,
    )


rubrics = [
    _rubric(
        "019c4e7a-47a2-7889-858c-14ec6323b7ab",
        "Agent Rubric",
        "Rubric for evaluating agent agent performance",
    ),
    _rubric(
        "019c4e7a-479e-7b34-ba0e-58eab09e1f44",
        "Auth Rubric",
        "Rubric for evaluating auth agent performance",
    ),
    _rubric(
        "cc000002-0000-0000-0000-000000000002",
        "Benchmark Rubric",
        "Rubric for evaluating benchmark performance",
    ),
    _rubric(
        "019c4e7a-47a6-7948-affd-c0cea22aa769",
        "Chat Agent Rubric",
        "Rubric for evaluating chat agent agent performance",
    ),
    _rubric(
        "019c4e7a-47a1-7181-91be-42dc22179f81",
        "Cohort Rubric",
        "Rubric for evaluating cohort agent performance",
    ),
    _rubric(
        "019c4e7a-47a0-75eb-bdef-04fc7d4ce874",
        "Department Rubric",
        "Rubric for evaluating department agent performance",
    ),
    _rubric(
        "019c4e7a-479b-7d95-900b-3d38c946f3e5",
        "Document Rubric",
        "Rubric for evaluating document agent performance",
    ),
    _rubric(
        "019c4e7a-47a7-7545-862f-550706edd07c",
        "Eval Rubric",
        "Rubric for evaluating eval agent performance",
    ),
    _rubric(
        "019c4e7a-47a8-7e79-8bb9-743b68c9ee34",
        "Field Rubric",
        "Rubric for evaluating field agent performance",
    ),
    _rubric(
        "019c4e7a-47a8-7268-b6f9-97e720452517",
        "Grade Agent Rubric",
        "Rubric for evaluating grade agent agent performance",
    ),
    _rubric(
        "019c4e7a-47a3-76d0-802d-a581b9796d16",
        "Model Rubric",
        "Rubric for evaluating model agent performance",
    ),
    _rubric(
        "019c4e7a-479d-7a1c-b18b-0ba094f7c69f",
        "Parameter Rubric",
        "Rubric for evaluating parameter agent performance",
    ),
    _rubric(
        "019c4e7a-47a5-715d-baa4-84a8098ef9c6",
        "Persona Rubric",
        "Rubric for evaluating persona agent performance",
    ),
    _rubric(
        "019c4e7a-479f-7ab3-a251-dd33cd6d1328",
        "Profile Rubric",
        "Rubric for evaluating profile agent performance",
    ),
    _rubric(
        "019c4e7a-4794-733c-a828-56101d490e0c",
        "Provider Rubric",
        "Rubric for evaluating provider agent performance",
    ),
    _rubric(
        "019c4e7a-479c-7c30-a6da-b82b7dea8201",
        "Rubric Rubric",
        "Rubric for evaluating rubric agent performance",
    ),
    _rubric(
        "019c4e7a-479a-7a07-8165-81965e3f9c16",
        "Scenario Rubric",
        "Rubric for evaluating scenario agent performance",
    ),
    _rubric(
        "019c4e7a-47a1-7cc7-be5e-21b245e26939",
        "Setting Rubric",
        "Rubric for evaluating setting agent performance",
    ),
    _rubric(
        "019c4e7a-47a5-7d8e-8097-ae8bf9f8d2ad",
        "Simulation Rubric",
        "Rubric for evaluating simulation agent performance",
    ),
    _rubric(
        "019c4e7a-47a4-7540-aecd-d7a1d243643d",
        "Tool Rubric",
        "Rubric for evaluating tool agent performance",
    ),
    _rubric(
        "cc000001-0000-0000-0000-000000000001",
        "Training Rubric",
        "Rubric for evaluating training performance",
    ),
]
