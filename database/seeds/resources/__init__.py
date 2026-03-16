"""Resource seed module definitions.

Execution order matters: colors and icons must come before roles
(which references them via icon_id/color_id).
"""

MODULES = [
    "colors",
    "icons",
    "flags",
    "roles",
    "modalities",
    "qualities",
    "thresholds",
    "points",
    "request_limits",
    "voices",
    "pricing",
    "reasoning_levels",
    "temperature_levels",
    "operations",
    "artifacts",
    "standard_groups",
    "standards",
    "keys",
    "items",
]
