"""Operation resource seeds.

46 rows defining the available API operations.
"""

from uuid import UUID

operations = [
    # Standard CRUD
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
    dict(id=UUID("019d0000-0001-7000-8000-000000000033"), operation="csv"),
    # Attempt/test state machine
    dict(id=UUID("019d0000-0001-7000-8000-000000000012"), operation="start"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000013"), operation="next"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000014"), operation="end"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000015"), operation="end_all"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000016"), operation="message"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000017"), operation="grade"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000018"), operation="stop"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000019"), operation="response"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000020"), operation="previous"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000022"), operation="archive"),
    # Image
    dict(id=UUID("019d0000-0001-7000-8000-000000000040"), operation="image_upload"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000041"), operation="image_download"),
    # Video
    dict(id=UUID("019d0000-0001-7000-8000-000000000042"), operation="video_upload"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000043"), operation="video_download"),
    # Text
    dict(id=UUID("019d0000-0001-7000-8000-000000000044"), operation="text_upload"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000045"), operation="text_download"),
    # File
    dict(id=UUID("019d0000-0001-7000-8000-000000000046"), operation="file_upload"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000047"), operation="file_download"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000048"), operation="file_preview"),
    # Audio
    dict(id=UUID("019d0000-0001-7000-8000-000000000049"), operation="audio_start"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000050"), operation="audio_frame"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000051"), operation="audio_stop"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000052"), operation="audio_mute"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000053"), operation="audio_upload"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000054"), operation="audio_download"),
    # Call
    dict(id=UUID("019d0000-0001-7000-8000-000000000055"), operation="call_download"),
    # Artifact-specific
    dict(id=UUID("019d0000-0001-7000-8000-000000000024"), operation="run"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000025"), operation="generate"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000026"), operation="problem"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000027"), operation="resolve"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000028"), operation="emulate"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000029"), operation="context"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000030"), operation="decrypt"),
    dict(id=UUID("019d0000-0001-7000-8000-000000000031"), operation="unemulate"),
]
