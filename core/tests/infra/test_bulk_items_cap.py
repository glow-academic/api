"""Resource-exhaustion guard: bulk create requests cap their item list.

Every bulk-create endpoint loops over the request's item list doing per-item
DB work (value resolution + denormalized snapshot + junction writes, several
inside one transaction). An unbounded list lets one authenticated request
fan out arbitrarily many DB round trips and hold a transaction open for an
unbounded time — a resource-exhaustion DoS. Pydantic ``max_length`` rejects
oversized lists with a 422 before any DB work runs.

This is a pure model-validation test — the request model + its bulk-list
field name are the explicit deps, passed in via parametrize. No DB/redis.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.infra.shared_types import MAX_BULK_ITEMS

from app.infra.agent.types import CreateAgentApiRequest
from app.infra.auth.types import CreateAuthApiRequest
from app.infra.cohort.types import CreateCohortApiRequest
from app.infra.department.types import CreateDepartmentApiRequest
from app.infra.document.types import CreateDocumentApiRequest
from app.infra.eval.types import CreateEvalApiRequest
from app.infra.field.types import CreateFieldApiRequest
from app.infra.model.types import CreateModelApiRequest
from app.infra.parameter.types import CreateParameterApiRequest
from app.infra.persona.types import CreatePersonaApiRequest
from app.infra.profile.types import CreateProfileApiRequest
from app.infra.provider.types import CreateProviderApiRequest
from app.infra.rubric.types import CreateRubricApiRequest
from app.infra.scenario.types import CreateScenarioApiRequest
from app.infra.setting.types import CreateSettingApiRequest
from app.infra.simulation.types import CreateSimulationApiRequest
from app.infra.tool.types import CreateToolApiRequest

# (request model, bulk-list field name). The item shape is a bare ``{}`` —
# every CreateXItem has all-optional fields (resolution happens server-side),
# so an empty dict is a structurally valid item for length validation.
BULK_CREATE_REQUESTS: list[tuple[type[BaseModel], str]] = [
    (CreateAgentApiRequest, "agents"),
    (CreateAuthApiRequest, "auths"),
    (CreateCohortApiRequest, "cohorts"),
    (CreateDepartmentApiRequest, "departments"),
    (CreateDocumentApiRequest, "documents"),
    (CreateEvalApiRequest, "evals"),
    (CreateFieldApiRequest, "fields"),
    (CreateModelApiRequest, "models"),
    (CreateParameterApiRequest, "parameters"),
    (CreatePersonaApiRequest, "personas"),
    (CreateProfileApiRequest, "profiles"),
    (CreateProviderApiRequest, "providers"),
    (CreateRubricApiRequest, "rubrics"),
    (CreateScenarioApiRequest, "scenarios"),
    (CreateSettingApiRequest, "settings"),
    (CreateSimulationApiRequest, "simulations"),
    (CreateToolApiRequest, "tools"),
]


@pytest.mark.parametrize("model, field", BULK_CREATE_REQUESTS)
def test_at_cap_accepted(model: type[BaseModel], field: str) -> None:
    """Exactly MAX_BULK_ITEMS is allowed (legitimate bulk import headroom)."""
    obj = model(**{field: [{} for _ in range(MAX_BULK_ITEMS)]})
    assert len(getattr(obj, field)) == MAX_BULK_ITEMS


@pytest.mark.parametrize("model, field", BULK_CREATE_REQUESTS)
def test_over_cap_rejected(model: type[BaseModel], field: str) -> None:
    """One past the cap is rejected before any handler/DB work runs."""
    with pytest.raises(ValidationError) as exc:
        model(**{field: [{} for _ in range(MAX_BULK_ITEMS + 1)]})
    # Pydantic flags the offending field with the 'too_long' error type.
    errors = exc.value.errors()
    assert any(
        e["type"] == "too_long" and field in e["loc"] for e in errors
    ), errors
