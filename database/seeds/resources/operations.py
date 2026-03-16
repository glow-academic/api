"""Operation resource seeds.

31 rows defining the available API operations (get, create, update, search,
delete, duplicate, draft, drafts, export, start, end, message, grade, etc.).
"""

from uuid import UUID

operations = [
    dict(id=UUID("019d0000-0001-7000-8000-000000000001"), operation="get"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000002"), operation="create"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000003"), operation="update"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000004"), operation="search"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000005"), operation="docs"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000006"), operation="delete"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000007"), operation="duplicate"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000008"), operation="draft"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000032"), operation="drafts"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000010"), operation="export"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000011"), operation="refresh"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000012"), operation="start"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000013"), operation="next"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000014"), operation="end"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000015"), operation="end_all"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000016"), operation="message"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000017"), operation="grade"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000018"), operation="stop"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000019"), operation="response"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000020"), operation="use_previous"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000021"), operation="audio"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000022"), operation="archive"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000023"), operation="events"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000024"), operation="run"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000025"), operation="generate"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000026"), operation="problem"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000027"), operation="resolve"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000028"), operation="emulate"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000029"), operation="context"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000030"), operation="decrypt"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000031"), operation="unemulate"),
]
