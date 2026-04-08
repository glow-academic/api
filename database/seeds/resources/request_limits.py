"""Request limit resource seeds.

Each row defines a rate limit with a count and a Postgres INTERVAL.
"""

from uuid import UUID

request_limits = [
    dict(id=UUID("019bb553-e77f-797c-ae44-544fbe10351b"), limit=10, interval="1 day"),
]
