"""Tests for document search — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.document.search import search_document_impl

pytestmark = pytest.mark.asyncio

_PROFILE_ID = uuid4()


@dataclass
class _FakeProfile:
    profiles_id = uuid4()
    name = "Test User"
    role = "admin"
    role_name = "Admin"
    role_description = "Administrator"
    role_artifacts = []
    primary_email = "test@test.com"
    emails = ["test@test.com"]
    primary_department_id = None
    department_ids = []
    settings_id = None
    request_limit = None
    request_limit_interval = None
    is_active = True
    session_id = None
    group_id = uuid4()
    role_level = 1
    role_permissions = []


class _FakeConn:
    async def execute(self, *a, **kw):
        pass

    async def fetch(self, *a, **kw):
        return []

    async def fetchval(self, *a, **kw):
        return None

    async def fetchrow(self, *a, **kw):
        return None

    def transaction(self):
        return self._FakeTx()

    class _FakeTx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass


class _FakePool:
    class _ctx:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, *a):
            pass

    def acquire(self):
        return self._ctx()


class TestAuth:
    async def test_raises_401_when_profile_not_found(self, monkeypatch):
        async def fake_resolve(*args, **kw):
            return None

        monkeypatch.setattr(
            "app.infra.document.search.resolve_profile_identity_context", fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await search_document_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, items=[],
            )
        assert exc_info.value.status_code == 401


class TestProfileResolved:
    async def test_profile_context_is_called(self, monkeypatch):
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.document.search.resolve_profile_identity_context", fake_resolve,
        )

        # We expect downstream errors after profile resolution succeeds
        # but verify profile resolution was actually called
        try:
            await search_document_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, items=[],
            )
        except Exception:
            pass  # downstream errors expected
        assert len(called) == 1


class TestImport:
    async def test_function_is_importable(self):
        assert callable(search_document_impl)


@dataclass
class _FakeArtifact:
    id: object
    name_ids: list
    files_ids: list
    flag_ids: list
    department_ids: list
    document_ids: list
    active: bool = True
    updated_at: object = None


@dataclass
class _FakeDocResource:
    id: object
    file_id: object
    text_id: object


@dataclass
class _FakeName:
    id: object
    name: str


@dataclass
class _FakePerm:
    active_scenario_count: int = 0


class TestContentIdResolution:
    """The library preview needs the document's canonical content ids.

    Content lives on ``documents_resource`` (file_id / text_id), reached via
    ``document_documents_junction``. The build must surface those — NOT the
    empty artifact-level ``document_files_junction`` — so the viewer has an id
    to fetch with. Regression guard for the "Failed to load document" bug.
    """

    async def test_search_surfaces_resolved_file_and_text_ids(self, monkeypatch):
        from app.infra.document import search as search_mod

        artifact_id = uuid4()
        resource_id = uuid4()
        file_id = uuid4()
        text_id = uuid4()
        name_id = uuid4()

        async def fake_profile(*a, **kw):
            return _FakeProfile()

        async def fake_search_documents(*a, **kw):
            return ([artifact_id], 1)

        async def fake_soft_calls(*a, **kw):
            return []

        async def fake_get_documents(*a, **kw):
            # Artifact carries NO artifact-level file junction (files_ids empty);
            # its content lives on the documents_resource it points to.
            return [
                _FakeArtifact(
                    id=artifact_id,
                    name_ids=[name_id],
                    files_ids=[],
                    flag_ids=[],
                    department_ids=[],
                    document_ids=[resource_id],
                )
            ]

        async def fake_get_document_resources(*a, **kw):
            return [_FakeDocResource(id=resource_id, file_id=file_id, text_id=text_id)]

        async def fake_get_names(*a, **kw):
            return [_FakeName(id=name_id, name="Academic Integrity Policy")]

        async def fake_empty(*a, **kw):
            return []

        async def fake_perm(*a, **kw):
            return _FakePerm()

        monkeypatch.setattr(search_mod, "resolve_profile_identity_context", fake_profile)
        monkeypatch.setattr(search_mod, "search_documents", fake_search_documents)
        monkeypatch.setattr(
            "app.tools.entries.soft_calls.search.search_soft_calls", fake_soft_calls
        )
        monkeypatch.setattr(search_mod, "get_documents", fake_get_documents)
        monkeypatch.setattr(
            search_mod, "get_document_resources", fake_get_document_resources
        )
        monkeypatch.setattr(search_mod, "get_names", fake_get_names)
        monkeypatch.setattr(search_mod, "get_uploads", fake_empty)
        monkeypatch.setattr(search_mod, "get_flags", fake_empty)
        monkeypatch.setattr(search_mod, "search_scenarios_resource", fake_empty)
        monkeypatch.setattr(search_mod, "search_fields_resource", fake_empty)
        monkeypatch.setattr(search_mod, "search_departments", fake_empty)
        monkeypatch.setattr(search_mod, "search_flags", fake_empty)
        monkeypatch.setattr(
            search_mod, "resolve_document_permissions_context", fake_perm
        )

        result = await search_mod._search_document_build(
            _FakePool(), object(), profile_id=_PROFILE_ID,
        )

        assert result.documents and len(result.documents) == 1
        doc = result.documents[0]
        assert doc.file_id == file_id
        assert doc.text_id == text_id
