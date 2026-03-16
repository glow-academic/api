"""Voice resource seeds.

8 rows defining available TTS voice options (verse, shimmer, sage, echo,
coral, ballad, ash, alloy).
"""

from uuid import UUID

voices = [
    dict(id=UUID("019bb58e-0ae2-7ee0-86f5-fcc485a51c96"), voice="verse"),
    dict(id=UUID("019bb58e-0ae3-71ed-b668-b9d470936e5a"), voice="shimmer"),
    dict(id=UUID("019bb58e-0ae3-72c3-9100-9245efb4d0fb"), voice="sage"),
    dict(id=UUID("019bb58e-0ae3-7386-9a7b-8ce481cbe63b"), voice="echo"),
    dict(id=UUID("019bb58e-0ae3-744b-b00b-5bb74063475c"), voice="coral"),
    dict(id=UUID("019bb58e-0ae3-7513-901e-051ff6eabeb7"), voice="ballad"),
    dict(id=UUID("019bb58e-0ae3-759a-9040-74de5c530f6d"), voice="ash"),
    dict(id=UUID("019bb58e-0ae3-75e7-b36c-3262763ac2a3"), voice="alloy"),
]
