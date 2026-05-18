"""Request limit resource seeds.

Each row defines a rate limit with a count and a Postgres INTERVAL.
"""

from database.seeds.ids import sid

request_limits = [
    dict(id=sid("request-limit/daily-10"), limit=10, interval="1 day"),
]
