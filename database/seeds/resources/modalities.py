"""Modality resource seeds.

10 rows defining input and output modalities (text, video, audio, image, call).
Each modality type appears twice: once for input and once for output.
"""

from database.seeds.ids import sid

modalities = [
    dict(
        id=sid("modality/text_out"), modality="text", is_input=False
    ),
    dict(
        id=sid("modality/video_out"),
        modality="video",
        is_input=False,
    ),
    dict(
        id=sid("modality/audio_out"),
        modality="audio",
        is_input=False,
    ),
    dict(
        id=sid("modality/image_out"),
        modality="image",
        is_input=False,
    ),
    dict(
        id=sid("modality/call_out"), modality="call", is_input=False
    ),
    dict(
        id=sid("modality/text_in"), modality="text", is_input=True
    ),
    dict(
        id=sid("modality/video_in"), modality="video", is_input=True
    ),
    dict(
        id=sid("modality/audio_in"), modality="audio", is_input=True
    ),
    dict(
        id=sid("modality/image_in"), modality="image", is_input=True
    ),
    dict(
        id=sid("modality/call_in"), modality="call", is_input=True
    ),
]
