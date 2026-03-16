"""Threshold resource seeds.

3 rows defining score thresholds for success (85), warning (80), and danger (70).
"""

from uuid import UUID

thresholds = [
    dict(id=UUID("019b995b-5308-7a8e-9d31-b08127742439"), value=85, type="success"),
    dict(id=UUID("019b995b-5309-714f-a5f6-5614613257b1"), value=80, type="warning"),
    dict(id=UUID("019b995b-5309-74df-991a-c28980b294f2"), value=70, type="danger"),
]
