"""Point resource seeds.

6 rows defining point values for total and pass score thresholds.
"""

from uuid import UUID

points = [
    dict(id=UUID("019b995b-52ec-7b7b-baf4-2c7b3162100b"), value=25, type="total"),
    dict(id=UUID("019b995b-52ed-7233-bdaf-88cbcc29083e"), value=20, type="pass"),
    dict(id=UUID("019b995b-52ec-7b7e-9cc6-35aae7c0fe5f"), value=20, type="pass"),
    dict(id=UUID("019b995b-52ed-7224-85a6-2fe8ff7b0c32"), value=16, type="total"),
    dict(id=UUID("019b995b-52ec-7b66-9bd8-f1c13b810392"), value=10, type="total"),
    dict(id=UUID("019b995b-52ed-7236-9af7-2d462ea8f059"), value=8, type="total"),
]
