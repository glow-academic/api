"""University parameter_field seed definitions.

Creates parameter_fields_resource entries linking each parameter to its fields.
These are the junction records that personas, scenarios, and documents reference
via parameter_field_ids.

Generated programmatically from parameters × their field_ids.
Both parameter_id and field_id are resource IDs (canonical approach).
"""

from database.seeds.ids import sid
from database.seeds.setups.university.parameters import parameters

# ---------------------------------------------------------------------------
# Build parameter_field entries from parameter defs
# ---------------------------------------------------------------------------

parameter_fields = []

for p in parameters:
    param_resource_id = p["resource_id"]

    for field_resource_id in p.get("field_ids", []):
        pf_id = sid(f"uni/parameter-field/{param_resource_id}/{field_resource_id}")
        parameter_fields.append(dict(
            id=pf_id,
            parameter_id=param_resource_id,
            field_id=field_resource_id,
        ))
