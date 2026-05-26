"""Operation resource seeds.

46 rows defining the available API operations.
"""

from database.seeds.ids import sid

operations = [
    # Standard CRUD
    dict(id=sid("operation/get"), operation="get"),
    dict(id=sid("operation/create"), operation="create"),
    dict(id=sid("operation/update"), operation="update"),
    dict(id=sid("operation/search"), operation="search"),
    dict(id=sid("operation/docs"), operation="docs"),
    dict(id=sid("operation/delete"), operation="delete"),
    dict(id=sid("operation/duplicate"), operation="duplicate"),
    dict(id=sid("operation/draft"), operation="draft"),
    dict(id=sid("operation/drafts"), operation="drafts"),
    dict(id=sid("operation/export"), operation="export"),
    dict(id=sid("operation/refresh"), operation="refresh"),
    dict(id=sid("operation/csv"), operation="csv"),
    # Attempt/test state machine
    dict(id=sid("operation/start"), operation="start"),
    dict(id=sid("operation/next"), operation="next"),
    dict(id=sid("operation/end"), operation="end"),
    dict(id=sid("operation/end_all"), operation="end_all"),
    dict(id=sid("operation/message"), operation="message"),
    dict(id=sid("operation/grade"), operation="grade"),
    dict(id=sid("operation/stop"), operation="stop"),
    dict(id=sid("operation/complete"), operation="complete"),
    dict(id=sid("operation/response"), operation="response"),
    dict(id=sid("operation/previous"), operation="previous"),
    dict(id=sid("operation/archive"), operation="archive"),
    # Image
    dict(id=sid("operation/image_upload"), operation="image_upload"),
    dict(id=sid("operation/image_download"), operation="image_download"),
    # Video
    dict(id=sid("operation/video_upload"), operation="video_upload"),
    dict(id=sid("operation/video_download"), operation="video_download"),
    # Text
    dict(id=sid("operation/text_upload"), operation="text_upload"),
    dict(id=sid("operation/text_download"), operation="text_download"),
    # File
    dict(id=sid("operation/file_upload"), operation="file_upload"),
    dict(id=sid("operation/file_download"), operation="file_download"),
    dict(id=sid("operation/file_preview"), operation="file_preview"),
    # Audio
    dict(id=sid("operation/audio_start"), operation="audio_start"),
    dict(id=sid("operation/audio_frame"), operation="audio_frame"),
    dict(id=sid("operation/audio_stop"), operation="audio_stop"),
    dict(id=sid("operation/audio_mute"), operation="audio_mute"),
    dict(id=sid("operation/audio_upload"), operation="audio_upload"),
    dict(id=sid("operation/audio_download"), operation="audio_download"),
    # Call
    dict(id=sid("operation/call_download"), operation="call_download"),
    # Artifact-specific
    dict(id=sid("operation/run"), operation="run"),
    dict(id=sid("operation/trace"), operation="trace"),
    dict(id=sid("operation/invocation_complete"), operation="invocation_complete"),
    dict(id=sid("operation/invocations"), operation="invocations"),
    dict(id=sid("operation/sessions"), operation="sessions"),
    dict(id=sid("operation/generate"), operation="generate"),
    dict(id=sid("operation/problem"), operation="problem"),
    dict(id=sid("operation/resolve"), operation="resolve"),
    dict(id=sid("operation/emulate"), operation="emulate"),
    dict(id=sid("operation/context"), operation="context"),
    dict(id=sid("operation/decrypt"), operation="decrypt"),
    dict(id=sid("operation/unemulate"), operation="unemulate"),
]
