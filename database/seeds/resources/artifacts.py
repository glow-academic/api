"""Artifact resource seeds.

33 rows defining the available API artifact types (one per v5/api/main/ folder).
"""

from database.seeds.ids import sid

artifacts = [
    dict(id=sid("artifact/activity"), artifact="activity"),
    dict(id=sid("artifact/agent"), artifact="agent"),
    dict(id=sid("artifact/attempt"), artifact="attempt"),
    dict(id=sid("artifact/auth"), artifact="auth"),
    dict(id=sid("artifact/benchmark"), artifact="benchmark"),
    dict(id=sid("artifact/chat"), artifact="chat"),
    dict(id=sid("artifact/cohort"), artifact="cohort"),
    dict(id=sid("artifact/dashboard"), artifact="dashboard"),
    dict(id=sid("artifact/department"), artifact="department"),
    dict(id=sid("artifact/document"), artifact="document"),
    dict(id=sid("artifact/eval"), artifact="eval"),
    dict(id=sid("artifact/field"), artifact="field"),
    dict(id=sid("artifact/group"), artifact="group"),
    dict(id=sid("artifact/health"), artifact="health"),
    dict(id=sid("artifact/home"), artifact="home"),
    dict(id=sid("artifact/invocation"), artifact="invocation"),
    dict(id=sid("artifact/leaderboard"), artifact="leaderboard"),
    dict(id=sid("artifact/model"), artifact="model"),
    dict(id=sid("artifact/parameter"), artifact="parameter"),
    dict(id=sid("artifact/persona"), artifact="persona"),
    dict(id=sid("artifact/practice"), artifact="practice"),
    dict(id=sid("artifact/pricing"), artifact="pricing"),
    dict(id=sid("artifact/profile"), artifact="profile"),
    dict(id=sid("artifact/provider"), artifact="provider"),
    dict(id=sid("artifact/record"), artifact="record"),
    dict(id=sid("artifact/reports"), artifact="reports"),
    dict(id=sid("artifact/rubric"), artifact="rubric"),
    dict(id=sid("artifact/scenario"), artifact="scenario"),
    dict(id=sid("artifact/session"), artifact="session"),
    dict(id=sid("artifact/setting"), artifact="setting"),
    dict(id=sid("artifact/simulation"), artifact="simulation"),
    dict(id=sid("artifact/test"), artifact="test"),
    dict(id=sid("artifact/tool"), artifact="tool"),
]
