"""Threshold resource seeds.

3 rows defining score thresholds for success (85), warning (80), and danger (70).
"""

from database.seeds.ids import sid

thresholds = [
    dict(id=sid("threshold/85"), value=85, type="success"),
    dict(id=sid("threshold/80"), value=80, type="warning"),
    dict(id=sid("threshold/70"), value=70, type="danger"),
]
