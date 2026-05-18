"""Temperature levels — fixed set from 0.0 to 2.0 in 0.01 increments.

Models reference a subset by specifying {min, max} in config.
201 total levels, shared across all models.
"""

from database.seeds.ids import sid

temperature_levels = [
    dict(id=sid(f"temperature/{round(i * 0.01, 2)}"), temperature=round(i * 0.01, 2))
    for i in range(201)  # 0.00 to 2.00
]

# Lookup: temperature value → UUID
TEMPERATURE_LOOKUP = {round(t["temperature"], 2): t["id"] for t in temperature_levels}
