"""Request limit resource seeds.

1 row defining the default daily request limit.
"""

from uuid import UUID

request_limits = [
    dict(id=UUID("019bb553-e77f-797c-ae44-544fbe10351b"), requests_per_day=10),
]
