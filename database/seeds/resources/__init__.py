"""Resource seed module definitions.

Execution order matters: colors and icons must come before roles
(which references them via icon_id/color_id).

Dynamic resources (temperature_levels, pricing, voices) are generated
from model configs in models.py and seeded separately by the runner.
"""

MODULES = [
    "colors",
    "icons",
    "flags",
    "permissions",
    "roles",
    "modalities",
    "qualities",
    "thresholds",
    "points",
    "request_limits",
    "reasoning_levels",
    "temperature_levels",
    "standard_groups",
    "standards",
    "items",
]
