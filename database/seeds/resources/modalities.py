"""Modality resource seeds.

10 rows defining input and output modalities (text, video, audio, image, call).
Each modality type appears twice: once for input and once for output.
"""

from uuid import UUID

modalities = [
    dict(
        id=UUID("019bbce5-e606-77f1-abf8-78df7462af03"), modality="text", is_input=False
    ),
    dict(
        id=UUID("019bbce5-e607-7bc4-a6b0-a4218bc8e5f8"),
        modality="video",
        is_input=False,
    ),
    dict(
        id=UUID("019bbce5-e608-7d5a-b937-0a22697e3f8b"),
        modality="audio",
        is_input=False,
    ),
    dict(
        id=UUID("019bbce5-e609-750d-90c6-cb39f1266e18"),
        modality="image",
        is_input=False,
    ),
    dict(
        id=UUID("019bbce5-e609-7efe-8549-87dd267f086a"), modality="call", is_input=False
    ),
    dict(
        id=UUID("019c47d6-6c45-754d-9669-73c9882d1a66"), modality="text", is_input=True
    ),
    dict(
        id=UUID("019c47d6-6c45-75df-923a-6b23040e63b3"), modality="video", is_input=True
    ),
    dict(
        id=UUID("019c47d6-6c45-75ed-b882-53a18d4f5db6"), modality="audio", is_input=True
    ),
    dict(
        id=UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"), modality="image", is_input=True
    ),
    dict(
        id=UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"), modality="call", is_input=True
    ),
]
