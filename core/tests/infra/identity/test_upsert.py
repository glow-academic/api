"""Tests for infra.auth.upsert using explicit collaborator boundaries."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.infra.identity.upsert import UpsertProfileResult, resolve_profile_upsert


class _TransactionContext:
    def __init__(self, conn: object) -> None:
        self._conn = conn

    async def __aenter__(self) -> object:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _Connection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    def transaction(self) -> _TransactionContext:
        return _TransactionContext(self)

    async def execute(self, query: str, *args: object) -> str:
        self.executed.append((query, args))
        return "SELECT 1"


class _AcquireContext:
    def __init__(self, conn: _Connection) -> None:
        self._conn = conn

    async def __aenter__(self) -> _Connection:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakePool:
    def __init__(self) -> None:
        self.conn = _Connection()

    def acquire(self) -> _AcquireContext:
        return _AcquireContext(self.conn)


def _identity(*, role: str = "Super Administrator") -> SimpleNamespace:
    return SimpleNamespace(role=role, profiles_id=uuid4())


def _name_resource(*, id: UUID | None = None, name: str = "Test") -> SimpleNamespace:
    return SimpleNamespace(id=id or uuid4(), name=name)


def _email_resource(
    *, id: UUID | None = None, email: str = "test@example.com"
) -> SimpleNamespace:
    return SimpleNamespace(id=id or uuid4(), email=email)


def _role_resource(*, id: UUID | None = None, role: str = "member") -> SimpleNamespace:
    return SimpleNamespace(id=id or uuid4(), role=role, name=role)


def _flag_resource(
    *, id: UUID | None = None, name: str = "profile_active"
) -> SimpleNamespace:
    return SimpleNamespace(id=id or uuid4(), name=name)


@pytest.mark.asyncio
class TestResolveProfileUpsert:
    async def test_creates_new_profile(self) -> None:
        pool = FakePool()
        name_id = uuid4()
        email_id = uuid4()
        role_id = uuid4()
        flag_id = uuid4()
        snapshot_id = uuid4()
        profile_id = uuid4()
        session_id = uuid4()
        calls: dict[str, object] = {}

        async def fake_create_name(conn, name, redis):
            calls["name"] = name
            return _name_resource(id=name_id, name=name)

        async def fake_create_email(conn, email, redis):
            calls.setdefault("emails", []).append(email)
            return _email_resource(id=email_id, email=email)

        async def fake_search_roles(conn, redis, **kwargs):
            return [_role_resource(id=role_id, role="member")]

        async def fake_search_flags(conn, redis, **kwargs):
            return [_flag_resource(id=flag_id)]

        async def fake_search_profiles(conn, **kwargs):
            calls["search_profiles"] = kwargs
            return [], 0

        async def fake_create_snapshot(conn, redis, **kwargs):
            calls["snapshot"] = kwargs
            return snapshot_id

        async def fake_create_profile_artifact(conn, **kwargs):
            calls["create_profile"] = kwargs
            return SimpleNamespace(id=profile_id)

        async def fake_create_session(conn, profiles_resource_id):
            calls["session"] = profiles_resource_id
            return SimpleNamespace(id=session_id)

        result = await resolve_profile_upsert(
            pool,
            None,
            name="John Doe",
            emails=["john@example.com"],
            role="member",
            current_profile_id=None,
            create_name_fn=fake_create_name,
            create_email_fn=fake_create_email,
            search_roles_fn=fake_search_roles,
            search_flags_fn=fake_search_flags,
            search_profiles_fn=fake_search_profiles,
            create_snapshot_fn=fake_create_snapshot,
            create_profile_artifact_fn=fake_create_profile_artifact,
            create_session_fn=fake_create_session,
        )

        assert isinstance(result, UpsertProfileResult)
        assert result.created is True
        assert result.profile_id == profile_id
        assert result.session_id == session_id
        assert calls["search_profiles"] == {
            "email_ids": [email_id],
            "active_only": False,
            "limit_count": 1,
        }
        assert calls["create_profile"] == {
            "id": None,
            "name_id": name_id,
            "email_ids": [email_id],
            "role_ids": [role_id],
            "department_ids": None,
            "primary_departments_id": None,
            "flag_ids": [flag_id],
            "profile_ids": [snapshot_id],
            "redis": None,
        }
        assert calls["session"] == snapshot_id

    async def test_passes_department_ids_to_create_path(self) -> None:
        pool = FakePool()
        department_id = uuid4()
        snapshot_id = uuid4()
        create_calls: list[dict[str, object]] = []

        async def fake_create_profile_artifact(conn, **kwargs):
            create_calls.append(kwargs)
            return SimpleNamespace(id=uuid4())

        await resolve_profile_upsert(
            pool,
            None,
            name="Jane",
            emails=["jane@example.com"],
            role="member",
            department_ids=[department_id],
            create_name_fn=lambda conn, name, redis: _await_value(_name_resource()),
            create_email_fn=lambda conn, email, redis: _await_value(_email_resource()),
            search_roles_fn=lambda conn, redis, **kwargs: _await_value(
                [_role_resource()]
            ),
            search_flags_fn=lambda conn, redis, **kwargs: _await_value(
                [_flag_resource()]
            ),
            search_profiles_fn=lambda conn, **kwargs: _await_value(([], 0)),
            create_snapshot_fn=lambda conn, redis, **kwargs: _await_value(snapshot_id),
            create_profile_artifact_fn=fake_create_profile_artifact,
            create_session_fn=lambda conn, profiles_resource_id: _await_value(
                SimpleNamespace(id=uuid4())
            ),
        )

        assert len(create_calls) == 1
        assert create_calls[0]["department_ids"] == [department_id]
        assert create_calls[0]["profile_ids"] == [snapshot_id]

    async def test_updates_existing_profile(self) -> None:
        pool = FakePool()
        existing_id = uuid4()
        snapshot_id = uuid4()
        updates: list[tuple[UUID, dict[str, object]]] = []

        async def fake_update_profile_artifact(conn, profile_id_arg, **kwargs):
            updates.append((profile_id_arg, kwargs))
            return SimpleNamespace(id=profile_id_arg)

        result = await resolve_profile_upsert(
            pool,
            None,
            name="Updated Name",
            emails=["existing@example.com"],
            role="member",
            create_name_fn=lambda conn, name, redis: _await_value(_name_resource()),
            create_email_fn=lambda conn, email, redis: _await_value(_email_resource()),
            search_roles_fn=lambda conn, redis, **kwargs: _await_value(
                [_role_resource()]
            ),
            search_flags_fn=lambda conn, redis, **kwargs: _await_value(
                [_flag_resource()]
            ),
            search_profiles_fn=lambda conn, **kwargs: _await_value(([existing_id], 1)),
            create_snapshot_fn=lambda conn, redis, **kwargs: _await_value(snapshot_id),
            update_profile_artifact_fn=fake_update_profile_artifact,
            create_session_fn=lambda conn, profiles_resource_id: _await_value(
                SimpleNamespace(id=uuid4())
            ),
        )

        assert result.created is False
        assert result.profile_id == existing_id
        assert len(updates) == 1
        updated_profile_id, kwargs = updates[0]
        assert updated_profile_id == existing_id
        assert kwargs["profile_ids"] == [snapshot_id]
        assert kwargs["department_ids"] is None
        assert len(kwargs["email_ids"]) == 1
        assert len(kwargs["role_ids"]) == 1

    async def test_admin_cannot_assign_superadmin(self) -> None:
        pool = FakePool()

        async def fake_identity(pool_arg, profile_id_arg, redis, *, bypass_cache=False):
            return _identity(role="Administrator")

        with pytest.raises(ValueError, match="cannot assign role"):
            await resolve_profile_upsert(
                pool,
                None,
                name="Test",
                emails=["test@example.com"],
                role="Super Administrator",
                current_profile_id=uuid4(),
                resolve_profile_identity_fn=fake_identity,
            )

    async def test_role_not_found_raises(self) -> None:
        pool = FakePool()

        with pytest.raises(ValueError, match="Role 'nonexistent' not found"):
            await resolve_profile_upsert(
                pool,
                None,
                name="Test",
                emails=["test@example.com"],
                role="nonexistent",
                create_name_fn=lambda conn, name, redis: _await_value(_name_resource()),
                create_email_fn=lambda conn, email, redis: _await_value(
                    _email_resource()
                ),
                search_roles_fn=lambda conn, redis, **kwargs: _await_value([]),
                search_flags_fn=lambda conn, redis, **kwargs: _await_value([]),
            )

    async def test_creates_all_email_resources(self) -> None:
        pool = FakePool()
        email_ids = [uuid4(), uuid4(), uuid4()]
        created_email_inputs: list[str] = []
        create_calls: list[dict[str, object]] = []

        async def fake_create_email(conn, email, redis):
            created_email_inputs.append(email)
            idx = len(created_email_inputs) - 1
            return _email_resource(id=email_ids[idx], email=email)

        async def fake_create_profile_artifact(conn, **kwargs):
            create_calls.append(kwargs)
            return SimpleNamespace(id=uuid4())

        await resolve_profile_upsert(
            pool,
            None,
            name="Multi Email",
            emails=["a@test.com", "b@test.com", "c@test.com"],
            role="member",
            create_name_fn=lambda conn, name, redis: _await_value(_name_resource()),
            create_email_fn=fake_create_email,
            search_roles_fn=lambda conn, redis, **kwargs: _await_value(
                [_role_resource()]
            ),
            search_flags_fn=lambda conn, redis, **kwargs: _await_value(
                [_flag_resource()]
            ),
            search_profiles_fn=lambda conn, **kwargs: _await_value(([], 0)),
            create_snapshot_fn=lambda conn, redis, **kwargs: _await_value(uuid4()),
            create_profile_artifact_fn=fake_create_profile_artifact,
            create_session_fn=lambda conn, profiles_resource_id: _await_value(
                SimpleNamespace(id=uuid4())
            ),
        )

        assert created_email_inputs == ["a@test.com", "b@test.com", "c@test.com"]
        assert len(create_calls) == 1
        assert create_calls[0]["email_ids"] == email_ids


    async def test_takes_advisory_lock_on_primary_email(self) -> None:
        # C1-A: first-create must be serialized on the primary email so two
        # concurrent first-logins can't both create a profile.
        pool = FakePool()

        await resolve_profile_upsert(
            pool,
            None,
            name="Locked",
            emails=["a@test.com", "primary@test.com"],
            role="member",
            primary_email_index=1,
            create_name_fn=lambda conn, name, redis: _await_value(_name_resource()),
            create_email_fn=lambda conn, email, redis: _await_value(_email_resource()),
            search_roles_fn=lambda conn, redis, **kwargs: _await_value(
                [_role_resource()]
            ),
            search_flags_fn=lambda conn, redis, **kwargs: _await_value(
                [_flag_resource()]
            ),
            search_profiles_fn=lambda conn, **kwargs: _await_value(([], 0)),
            create_snapshot_fn=lambda conn, redis, **kwargs: _await_value(uuid4()),
            create_profile_artifact_fn=lambda conn, **kwargs: _await_value(
                SimpleNamespace(id=uuid4())
            ),
            create_session_fn=lambda conn, profiles_resource_id: _await_value(
                SimpleNamespace(id=uuid4())
            ),
        )

        lock_calls = [
            args
            for query, args in pool.conn.executed
            if "pg_advisory_xact_lock" in query
        ]
        assert len(lock_calls) == 1
        # Keyed on the PRIMARY email (index 1), not the first email.
        assert lock_calls[0] == ("primary@test.com",)

    async def test_concurrent_first_logins_converge_on_one_profile(self) -> None:
        # C1-A: model the race — the lock-winner creates a profile; once it
        # commits, the loser's search-by-email hits the winner's profile and it
        # takes the UPDATE path. Exactly one profile is created, both converge.
        import asyncio

        pool = FakePool()
        winner_profile_id = uuid4()
        email_id = uuid4()
        # Shared "DB" state mutated by the winner's create; the lock guarantees
        # the loser observes it on its subsequent search.
        store: dict[str, list[UUID]] = {"profiles": []}
        create_count = {"n": 0}

        async def fake_search_profiles(conn, **kwargs):
            return (list(store["profiles"]), len(store["profiles"]))

        async def fake_create_profile_artifact(conn, **kwargs):
            create_count["n"] += 1
            store["profiles"].append(winner_profile_id)
            return SimpleNamespace(id=winner_profile_id)

        updated_ids: list[UUID] = []

        async def fake_update_profile_artifact(conn, profile_id_arg, **kwargs):
            updated_ids.append(profile_id_arg)
            return SimpleNamespace(id=profile_id_arg)

        async def one_login() -> UpsertProfileResult:
            return await resolve_profile_upsert(
                pool,
                None,
                name="Same Human",
                emails=["same@test.com"],
                role="member",
                create_name_fn=lambda conn, name, redis: _await_value(
                    _name_resource()
                ),
                create_email_fn=lambda conn, email, redis: _await_value(
                    _email_resource(id=email_id, email=email)
                ),
                search_roles_fn=lambda conn, redis, **kwargs: _await_value(
                    [_role_resource()]
                ),
                search_flags_fn=lambda conn, redis, **kwargs: _await_value(
                    [_flag_resource()]
                ),
                search_profiles_fn=fake_search_profiles,
                create_snapshot_fn=lambda conn, redis, **kwargs: _await_value(uuid4()),
                create_profile_artifact_fn=fake_create_profile_artifact,
                update_profile_artifact_fn=fake_update_profile_artifact,
                create_session_fn=lambda conn, profiles_resource_id: _await_value(
                    SimpleNamespace(id=uuid4())
                ),
            )

        # Serial execution models the post-lock ordering the advisory lock
        # enforces in Postgres (the loser cannot run its search until the
        # winner commits). Both calls share the same store.
        first = await one_login()
        second = await one_login()

        assert create_count["n"] == 1
        assert first.created is True
        assert second.created is False
        # Race-loser converges on the SAME profile (no duplicate identity).
        assert first.profile_id == winner_profile_id
        assert second.profile_id == winner_profile_id
        assert updated_ids == [winner_profile_id]


async def _await_value(value):
    return value
