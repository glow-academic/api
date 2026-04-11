"""University conditional parameter seed definitions.

Conditional parameters define cascading behavior: when a field is selected,
additional parameters become visible. For example, selecting "aggressive"
(a Temperament field) shows the Intensity parameter.

Each conditional_parameter links to a parameter that should be shown.
Fields reference conditional_parameter_ids to trigger the cascade.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.parameters import (
    P_CLASS_RESOURCE, P_CONCEPTS_RESOURCE, P_INTENSITY_RESOURCE,
    P_ROLE_RESOURCE, P_TEMPERAMENT_RESOURCE,
)

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

CP_INTENSITY = sid("uni/conditional-parameter/intensity")
CP_TEMPERAMENT = sid("uni/conditional-parameter/temperament")
CP_ROLE = sid("uni/conditional-parameter/role")
CP_CLASS = sid("uni/conditional-parameter/class")
CP_CONCEPTS = sid("uni/conditional-parameter/concepts")

# ---------------------------------------------------------------------------
# Conditional parameter definitions
# ---------------------------------------------------------------------------

conditional_parameters = [
    dict(id=CP_INTENSITY, parameter_id=P_INTENSITY_RESOURCE),
    dict(id=CP_TEMPERAMENT, parameter_id=P_TEMPERAMENT_RESOURCE),
    dict(id=CP_ROLE, parameter_id=P_ROLE_RESOURCE),
    dict(id=CP_CLASS, parameter_id=P_CLASS_RESOURCE),
    dict(id=CP_CONCEPTS, parameter_id=P_CONCEPTS_RESOURCE),
]
