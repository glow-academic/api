"""Quality resource seeds.

3 rows defining quality tiers: low, medium, and high.
"""

from uuid import UUID

qualities = [
    dict(id=UUID("019bbce5-e5ff-7197-bd68-b0ff7b7508af"), quality="low"),
    dict(id=UUID("019bbce5-e600-773a-ac8b-7044ffed731c"), quality="medium"),
    dict(id=UUID("019bbce5-e600-7e7e-9a28-1182423e74a7"), quality="high"),
]
