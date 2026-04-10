"""Point resource seeds.

6 rows defining point values for total and pass score thresholds.
"""

from database.seeds.ids import sid

points = [
    dict(id=sid("point/total/25"), value=25, type="total"),
    dict(id=sid("point/pass/20"), value=20, type="pass"),
    dict(id=sid("point/pass/20.2"), value=20, type="pass"),
    dict(id=sid("point/total/16"), value=16, type="total"),
    dict(id=sid("point/total/10"), value=10, type="total"),
    dict(id=sid("point/total/8"), value=8, type="total"),
]
