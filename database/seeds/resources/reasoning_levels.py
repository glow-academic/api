"""Reasoning level resource seeds.

33 rows defining reasoning effort levels (none, minimal, low, medium, high)
across different AI model configurations.
"""

from database.seeds.ids import sid

reasoning_levels = [
    dict(id=sid("reasoning-level/none/0"), reasoning_level="none"),
    dict(id=sid("reasoning-level/minimal/0"), reasoning_level="minimal"),
    dict(id=sid("reasoning-level/low/0"), reasoning_level="low"),
    dict(id=sid("reasoning-level/medium/0"), reasoning_level="medium"),
    dict(id=sid("reasoning-level/high/0"), reasoning_level="high"),
    dict(id=sid("reasoning-level/none/1"), reasoning_level="none"),
    dict(id=sid("reasoning-level/minimal/1"), reasoning_level="minimal"),
    dict(id=sid("reasoning-level/low/1"), reasoning_level="low"),
    dict(id=sid("reasoning-level/medium/1"), reasoning_level="medium"),
    dict(id=sid("reasoning-level/high/1"), reasoning_level="high"),
    dict(id=sid("reasoning-level/none/2"), reasoning_level="none"),
    dict(id=sid("reasoning-level/low/2"), reasoning_level="low"),
    dict(id=sid("reasoning-level/medium/2"), reasoning_level="medium"),
    dict(id=sid("reasoning-level/high/2"), reasoning_level="high"),
    dict(id=sid("reasoning-level/none/3"), reasoning_level="none"),
    dict(id=sid("reasoning-level/low/3"), reasoning_level="low"),
    dict(id=sid("reasoning-level/medium/3"), reasoning_level="medium"),
    dict(id=sid("reasoning-level/high/3"), reasoning_level="high"),
    dict(id=sid("reasoning-level/none/4"), reasoning_level="none"),
    dict(id=sid("reasoning-level/low/4"), reasoning_level="low"),
    dict(id=sid("reasoning-level/medium/4"), reasoning_level="medium"),
    dict(id=sid("reasoning-level/high/4"), reasoning_level="high"),
    dict(id=sid("reasoning-level/high/5"), reasoning_level="high"),
    dict(id=sid("reasoning-level/medium/5"), reasoning_level="medium"),
    dict(id=sid("reasoning-level/low/5"), reasoning_level="low"),
    dict(id=sid("reasoning-level/minimal/2"), reasoning_level="minimal"),
    dict(id=sid("reasoning-level/none/5"), reasoning_level="none"),
    dict(id=sid("reasoning-level/high/6"), reasoning_level="high"),
    dict(id=sid("reasoning-level/medium/6"), reasoning_level="medium"),
    dict(id=sid("reasoning-level/low/6"), reasoning_level="low"),
    dict(id=sid("reasoning-level/minimal/3"), reasoning_level="minimal"),
    dict(id=sid("reasoning-level/none/6"), reasoning_level="none"),
]
