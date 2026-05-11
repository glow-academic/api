"""Reasoning level resource seeds.

Five canonical rows — one per distinct effort value the model APIs
expose. ``minimal`` is OpenAI's GPT-5-era addition; older
``o1``/``o3`` reasoning models stop at the four-level surface
(``none``, ``low``, ``medium``, ``high``).

Every consumer (``models.py:_REASONING_LOOKUP``, deploy-config model
definitions, tests_analytics, etc.) resolves by name, so adding new
effort values means appending one row here — no per-model copies.
"""

from database.seeds.ids import sid

reasoning_levels = [
    dict(id=sid("reasoning-level/none/0"), reasoning_level="none"),
    dict(id=sid("reasoning-level/minimal/0"), reasoning_level="minimal"),
    dict(id=sid("reasoning-level/low/0"), reasoning_level="low"),
    dict(id=sid("reasoning-level/medium/0"), reasoning_level="medium"),
    dict(id=sid("reasoning-level/high/0"), reasoning_level="high"),
]
