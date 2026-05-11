"""Shared infrastructure for canonical file-modality export wrapping.

Every artifact-level export (`/attempt/export`, `/test/export`, `/system/export`)
wraps raw bytes via the 4-step file-modality chain documented in
``app.infra.persona.export``. The helper here is the single canonical
implementation — keeps the three artifact-level export endpoints in lock-step.
"""
