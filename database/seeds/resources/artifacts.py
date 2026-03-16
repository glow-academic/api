"""Artifact resource seeds.

33 rows defining the available API artifact types (one per v5/api/main/ folder).
"""

from uuid import UUID

artifacts = [
    dict(id=UUID("019d0000-0002-7000-8000-000000000001"), artifact="activity"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000002"), artifact="agent"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000003"), artifact="attempt"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000004"), artifact="auth"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000005"), artifact="benchmark"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000006"), artifact="chat"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000007"), artifact="cohort"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000008"), artifact="dashboard"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000009"), artifact="department"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000010"), artifact="document"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000011"), artifact="eval"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000012"), artifact="field"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000013"), artifact="group"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000014"), artifact="health"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000015"), artifact="home"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000016"), artifact="invocation"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000017"), artifact="leaderboard"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000018"), artifact="model"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000019"), artifact="parameter"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000020"), artifact="persona"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000021"), artifact="practice"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000022"), artifact="pricing"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000023"), artifact="profile"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000024"), artifact="provider"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000025"), artifact="record"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000026"), artifact="reports"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000027"), artifact="rubric"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000028"), artifact="scenario"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000029"), artifact="session"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000030"), artifact="setting"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000031"), artifact="simulation"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000032"), artifact="test"),
    dict(id=UUID("019d0000-0002-7000-8000-000000000033"), artifact="tool"),
]
