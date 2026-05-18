"""Quality resource seeds.

3 rows defining quality tiers: low, medium, and high.
"""

from database.seeds.ids import sid

qualities = [
    dict(id=sid("quality/low"), quality="low"),
    dict(id=sid("quality/medium"), quality="medium"),
    dict(id=sid("quality/high"), quality="high"),
]
