"""University parameter_field seed definitions.

Creates parameter_fields_resource entries linking each parameter to its fields.
These are the junction records that personas, scenarios, and documents reference
via parameter_field_ids.

Generated programmatically from parameters × their field_ids.
Uses field RESOURCE IDs (not artifact IDs) since parameter_fields_resource.field_id
FK references fields_resource.id.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.fields import fields as field_defs
from database.seeds.setups.university.parameters import parameters

# Build lookup: field artifact ID → field resource ID
_FIELD_RESOURCE_IDS = {}
for f in field_defs:
    _FIELD_RESOURCE_IDS[f["id"]] = f["resource_id"]

# ---------------------------------------------------------------------------
# Build parameter_field entries from parameter defs
# ---------------------------------------------------------------------------

parameter_fields = []

for p in parameters:
    param_resource_id = p["resource_id"]

    for field_artifact_id in p.get("field_ids", []):
        field_resource_id = _FIELD_RESOURCE_IDS.get(field_artifact_id)
        if not field_resource_id:
            continue  # skip if field not found

        # Deterministic ID from parameter resource + field resource
        pf_id = sid(f"uni/parameter-field/{param_resource_id}/{field_resource_id}")
        parameter_fields.append(dict(
            id=pf_id,
            parameter_id=param_resource_id,
            field_id=field_resource_id,
        ))
