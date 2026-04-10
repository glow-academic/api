"""Rubric module seeds.

21 base rubrics (one per artifact type). All share the same 5 standard groups,
25 standards, 3 points, and 2 flags — only differ in name, description, and IDs.
"""

from database.seeds.ids import sid

# Shared across all 21 rubrics
_POINT_IDS = [
    sid("point/total/25"),
    sid("point/pass/20"),
    sid("point/pass/20.2"),
]

_STANDARD_GROUP_IDS = [
    sid("standard-group/adaptability"),
    sid("standard-group/active-listening"),
    sid("standard-group/content-mastery"),
    sid("standard-group/communication"),
    sid("standard-group/time-management"),
]

_STANDARD_IDS = [
    # Active Listening
    sid("standard/active-listening/excellent"),
    sid("standard/active-listening/good"),
    sid("standard/active-listening/acceptable"),
    sid("standard/active-listening/marginal"),
    sid("standard/active-listening/poor"),
    # Time Management
    sid("standard/time-management/excellent"),
    sid("standard/time-management/good"),
    sid("standard/time-management/acceptable"),
    sid("standard/time-management/marginal"),
    sid("standard/time-management/poor"),
    # Adaptability
    sid("standard/adaptability/excellent"),
    sid("standard/adaptability/good"),
    sid("standard/adaptability/acceptable"),
    sid("standard/adaptability/marginal"),
    sid("standard/adaptability/poor"),
    # Communication
    sid("standard/communication/excellent"),
    sid("standard/communication/good"),
    sid("standard/communication/acceptable"),
    sid("standard/communication/marginal"),
    sid("standard/communication/poor"),
    # Content Mastery
    sid("standard/content-mastery/excellent"),
    sid("standard/content-mastery/good"),
    sid("standard/content-mastery/acceptable"),
    sid("standard/content-mastery/marginal"),
    sid("standard/content-mastery/poor"),
]


def _rubric(slug: str, name: str, description: str) -> dict:
    return dict(
        id=sid(f"rubric/{slug}"),
        name=name,
        description=description,
        point_ids=_POINT_IDS,
        standard_group_ids=_STANDARD_GROUP_IDS,
        standard_ids=_STANDARD_IDS,
    )


rubrics = [
    _rubric(
        "agent-rubric",
        "Agent Rubric",
        "Rubric for evaluating agent agent performance",
    ),
    _rubric(
        "auth-rubric",
        "Auth Rubric",
        "Rubric for evaluating auth agent performance",
    ),
    _rubric(
        "benchmark-rubric",
        "Benchmark Rubric",
        "Rubric for evaluating benchmark performance",
    ),
    _rubric(
        "chat-agent-rubric",
        "Chat Agent Rubric",
        "Rubric for evaluating chat agent agent performance",
    ),
    _rubric(
        "cohort-rubric",
        "Cohort Rubric",
        "Rubric for evaluating cohort agent performance",
    ),
    _rubric(
        "department-rubric",
        "Department Rubric",
        "Rubric for evaluating department agent performance",
    ),
    _rubric(
        "document-rubric",
        "Document Rubric",
        "Rubric for evaluating document agent performance",
    ),
    _rubric(
        "eval-rubric",
        "Eval Rubric",
        "Rubric for evaluating eval agent performance",
    ),
    _rubric(
        "field-rubric",
        "Field Rubric",
        "Rubric for evaluating field agent performance",
    ),
    _rubric(
        "grade-agent-rubric",
        "Grade Agent Rubric",
        "Rubric for evaluating grade agent agent performance",
    ),
    _rubric(
        "model-rubric",
        "Model Rubric",
        "Rubric for evaluating model agent performance",
    ),
    _rubric(
        "parameter-rubric",
        "Parameter Rubric",
        "Rubric for evaluating parameter agent performance",
    ),
    _rubric(
        "persona-rubric",
        "Persona Rubric",
        "Rubric for evaluating persona agent performance",
    ),
    _rubric(
        "profile-rubric",
        "Profile Rubric",
        "Rubric for evaluating profile agent performance",
    ),
    _rubric(
        "provider-rubric",
        "Provider Rubric",
        "Rubric for evaluating provider agent performance",
    ),
    _rubric(
        "rubric-rubric",
        "Rubric Rubric",
        "Rubric for evaluating rubric agent performance",
    ),
    _rubric(
        "scenario-rubric",
        "Scenario Rubric",
        "Rubric for evaluating scenario agent performance",
    ),
    _rubric(
        "setting-rubric",
        "Setting Rubric",
        "Rubric for evaluating setting agent performance",
    ),
    _rubric(
        "simulation-rubric",
        "Simulation Rubric",
        "Rubric for evaluating simulation agent performance",
    ),
    _rubric(
        "tool-rubric",
        "Tool Rubric",
        "Rubric for evaluating tool agent performance",
    ),
    _rubric(
        "training-rubric",
        "Training Rubric",
        "Rubric for evaluating training performance",
    ),
]
