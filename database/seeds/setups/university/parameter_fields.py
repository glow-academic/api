"""University parameter_field seed definitions.

Creates parameter_fields_resource entries linking each parameter to its fields.
These are the junction records that personas, scenarios, and documents reference
via parameter_field_ids.

Generated programmatically from parameters × their field_ids.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.parameters import parameters

# ---------------------------------------------------------------------------
# Build parameter_field entries from parameter defs
# ---------------------------------------------------------------------------

parameter_fields = []

for p in parameters:
    param_resource_id = p["resource_id"]
    # Derive a slug from the parameter's sid key
    # e.g. sid("uni/parameter-resource/temperament") → "temperament"
    param_slug = str(p["resource_id"]).replace("-", "")[:8]  # just for uniqueness

    for field_id in p.get("field_ids", []):
        # Deterministic ID from parameter + field
        pf_id = sid(f"uni/parameter-field/{p['resource_id']}/{field_id}")
        parameter_fields.append(dict(
            id=pf_id,
            parameter_id=param_resource_id,
            field_id=field_id,
        ))
