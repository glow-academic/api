"""End-to-end tests for the canonical profile HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor

from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.refresh import refresh_sessions


@dataclass(frozen=True)
class ProfileRouteResources:
    name_id: UUID
    name: str
    email_id: UUID
    email: str
    request_limit_id: UUID
    requests_per_day: int
    role_id: UUID
    department_id: UUID


async def _create_profile_route_resources(pool, redis_client) -> ProfileRouteResources:
    from app.tools.resources.departments.create import create_department
    from app.tools.resources.emails.create import create_email
    from app.tools.resources.names.create import create_name
    from app.tools.resources.request_limits.create import create_request_limit
    from app.tools.resources.roles.create import create_role

    tag = unique_tag()
    name = f"Route Profile {tag}"
    email = f"profile-route-{tag}@example.com"
    requests_per_day = 100

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        email_res = await create_email(conn, email, redis_client)
        request_limit_res = await create_request_limit(
            conn,
            requests_per_day,
            redis_client,
        )
        role_res = await create_role(
            conn,
            role="member",
            name=f"Route Member {tag}",
            description=f"Route member role {tag}",
            redis=redis_client,
        )
        department_res = await create_department(conn, redis=redis_client)

    return ProfileRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        email_id=email_res.id,
        email=email_res.email,
        request_limit_id=request_limit_res.id,
        requests_per_day=request_limit_res.requests_per_day,
        role_id=role_res.id,
        department_id=department_res.id,
    )


@pytest_asyncio.fixture
async def profile_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["profile", "agent", "persona"],
        group_name="profile-route",
        role_name_prefix="Profile Route Admin",
        role="superadmin",
    )


@pytest.mark.asyncio
class TestProfileRoute:
    async def test_create_profile_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_profile_route_client,
        profile_route_actor,
    ):
        resources = await _create_profile_route_resources(pool, redis_client)
        v5_profile_route_client.authenticate(
            profile_id=profile_route_actor.profile_id,
            session_id=profile_route_actor.session_id,
        )

        response = await v5_profile_route_client.client.post(
            "/v5/profiles/create",
            json={
                "profiles": [
                    {
                        "name_id": str(resources.name_id),
                        "request_limit_id": str(resources.request_limit_id),
                        "department_ids": [str(profile_route_actor.department_id)],
                        "email_ids": [str(resources.email_id)],
                        "role_ids": [str(resources.role_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "profiles"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["profile_id"] is not None

    async def test_get_profile_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_profile_route_client,
        profile_route_actor,
    ):
        created = await self._create_profile_via_route(
            pool,
            redis_client,
            v5_profile_route_client,
            profile_route_actor,
        )

        response = await v5_profile_route_client.client.post(
            "/v5/profiles/get",
            json={"target_profile_id": created["profile_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "profiles"
        payload = response.json()
        assert payload["actor_name"] == profile_route_actor.name
        assert payload["profile_exists"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]

    async def test_search_profile_route_returns_created_profile(
        self,
        pool,
        redis_client,
        v5_profile_route_client,
        profile_route_actor,
    ):
        created = await self._create_profile_via_route(
            pool,
            redis_client,
            v5_profile_route_client,
            profile_route_actor,
        )

        response = await v5_profile_route_client.client.post(
            "/v5/profiles/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(profile_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "profiles"
        payload = response.json()
        assert payload["actor_name"] == profile_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            profile["profile_id"] == created["profile_id"]
            for profile in payload["profiles"]
        )

    async def test_update_profile_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_profile_route_client,
        profile_route_actor,
    ):
        created = await self._create_profile_via_route(
            pool,
            redis_client,
            v5_profile_route_client,
            profile_route_actor,
        )
        updated = await _create_profile_route_resources(pool, redis_client)

        response = await v5_profile_route_client.client.post(
            "/v5/profiles/update",
            json={
                "profiles": [
                    {
                        "profile_id": created["profile_id"],
                        "name_id": str(updated.name_id),
                        "request_limit_id": str(updated.request_limit_id),
                        "department_ids": [str(profile_route_actor.department_id)],
                        "email_ids": [str(updated.email_id)],
                        "role_ids": [str(updated.role_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "profiles"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_delete_profile_route_soft_deletes_profile(
        self,
        pool,
        redis_client,
        v5_profile_route_client,
        profile_route_actor,
    ):
        created = await self._create_profile_via_route(
            pool,
            redis_client,
            v5_profile_route_client,
            profile_route_actor,
        )

        response = await v5_profile_route_client.client.post(
            "/v5/profiles/delete",
            json={"profile_ids": [created["profile_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "profiles"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_duplicate_profile_route_creates_new_profile(
        self,
        pool,
        redis_client,
        v5_profile_route_client,
        profile_route_actor,
    ):
        created = await self._create_profile_via_route(
            pool,
            redis_client,
            v5_profile_route_client,
            profile_route_actor,
        )

        response = await v5_profile_route_client.client.post(
            "/v5/profiles/duplicate",
            json={"target_profile_id": created["profile_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "profiles"
        payload = response.json()
        assert payload["success"] is True
        assert payload["profile_id"] != created["profile_id"]

    async def test_profile_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        v5_profile_route_client,
        profile_route_actor,
    ):
        resources = await _create_profile_route_resources(pool, redis_client)
        v5_profile_route_client.authenticate(
            profile_id=profile_route_actor.profile_id,
            session_id=profile_route_actor.session_id,
        )

        response = await v5_profile_route_client.client.patch(
            "/v5/profiles/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "department_ids": [str(profile_route_actor.department_id)],
                "email_ids": [str(resources.email_id)],
                "role_ids": [str(resources.role_id)],
                "request_limit_ids": [str(resources.request_limit_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "profiles,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["draft_id"] is not None
        assert payload["new_version"] == 1
        assert payload["form_state"]["name_id"] == str(resources.name_id)

    async def test_profile_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        v5_profile_route_client,
        profile_route_actor,
    ):
        resources = await _create_profile_route_resources(pool, redis_client)
        v5_profile_route_client.authenticate(
            profile_id=profile_route_actor.profile_id,
            session_id=profile_route_actor.session_id,
        )

        draft_response = await v5_profile_route_client.client.patch(
            "/v5/profiles/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "department_ids": [str(profile_route_actor.department_id)],
                "email_ids": [str(resources.email_id)],
                "role_ids": [str(resources.role_id)],
                "request_limit_ids": [str(resources.request_limit_id)],
            },
        )
        assert draft_response.status_code == 200, draft_response.text
        draft_id = draft_response.json()["draft_id"]

        response = await v5_profile_route_client.client.post(
            "/v5/profiles/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "profiles,drafts"
        payload = response.json()
        assert any(entry["id"] == draft_id for entry in (payload["entries"] or []))

    async def test_profile_docs_route_returns_composed_docs(
        self,
        v5_profile_route_client,
        profile_route_actor,
    ):
        v5_profile_route_client.authenticate(
            profile_id=profile_route_actor.profile_id,
            session_id=profile_route_actor.session_id,
        )

        response = await v5_profile_route_client.client.post(
            "/v5/profiles/docs",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "profile"
        assert payload["type"] == "artifact"
        assert payload["artifact"] is not None
        assert payload["api_operations"]

    async def test_profile_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        v5_profile_route_client,
        profile_route_actor,
    ):
        created = await self._create_profile_via_route(
            pool,
            redis_client,
            v5_profile_route_client,
            profile_route_actor,
        )

        response = await v5_profile_route_client.client.post(
            "/v5/profiles/export",
            json={"profile_export_id": created["profile_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] == 1

    async def test_profile_refresh_route_returns_invalidated_tags(
        self,
        v5_profile_route_client,
        profile_route_actor,
    ):
        v5_profile_route_client.authenticate(
            profile_id=profile_route_actor.profile_id,
            session_id=profile_route_actor.session_id,
        )

        response = await v5_profile_route_client.client.post(
            "/v5/profiles/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "profiles,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["invalidated_tags"] == ["profiles", "artifacts"]

    async def test_profile_context_route_returns_identity_bundle(
        self,
        v5_profile_route_client,
        profile_route_actor,
    ):
        v5_profile_route_client.authenticate(
            profile_id=profile_route_actor.profile_id,
            session_id=profile_route_actor.session_id,
        )

        response = await v5_profile_route_client.client.post(
            "/v5/context",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["id"] == str(profile_route_actor.profile_id)
        assert payload["name"] == profile_route_actor.name
        assert payload["role"] is not None
        assert payload["role_artifacts"] is not None

    async def test_profile_emulate_route_creates_grant(
        self,
        pool,
        redis_client,
        profile_identity_factory,
        v5_profile_route_client,
        profile_route_actor,
    ):
        target = await profile_identity_factory(
            name=f"Emulate Target {unique_tag()}",
            role=("member", "Member", "Member role"),
        )

        async with pool.acquire() as conn:
            await create_session(conn, profile_id=target.profile_resource_id)
            await refresh_sessions(conn)

        v5_profile_route_client.authenticate(
            profile_id=profile_route_actor.profile_id,
            session_id=profile_route_actor.session_id,
        )

        response = await v5_profile_route_client.client.post(
            "/v5/emulate",
            json={"target_profile_id": str(target.artifact_id), "ttl_minutes": 30},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "profile"
        payload = response.json()
        assert payload["allowed"] is True
        assert payload["grant_id"] is not None
        assert payload["expires_at"] is not None

    async def test_profile_unemulate_route_exits_innermost_grant(
        self,
        pool,
        redis_client,
        profile_identity_factory,
        v5_profile_route_client,
        profile_route_actor,
    ):
        target = await profile_identity_factory(
            name=f"Unemulate Target {unique_tag()}",
            role=("member", "Member", "Member role"),
        )

        async with pool.acquire() as conn:
            await create_session(conn, profile_id=target.profile_resource_id)
            await refresh_sessions(conn)

        v5_profile_route_client.authenticate(
            profile_id=profile_route_actor.profile_id,
            session_id=profile_route_actor.session_id,
        )

        emulate_response = await v5_profile_route_client.client.post(
            "/v5/emulate",
            json={"target_profile_id": str(target.artifact_id), "ttl_minutes": 30},
        )
        assert emulate_response.status_code == 200, emulate_response.text

        response = await v5_profile_route_client.client.post(
            "/v5/unemulate",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "profile"
        payload = response.json()
        assert payload["ok"] is True

    async def _create_profile_via_route(
        self,
        pool,
        redis_client,
        v5_profile_route_client,
        profile_route_actor,
    ) -> dict[str, str]:
        resources = await _create_profile_route_resources(pool, redis_client)
        v5_profile_route_client.authenticate(
            profile_id=profile_route_actor.profile_id,
            session_id=profile_route_actor.session_id,
        )

        response = await v5_profile_route_client.client.post(
            "/v5/profiles/create",
            json={
                "profiles": [
                    {
                        "name_id": str(resources.name_id),
                        "request_limit_id": str(resources.request_limit_id),
                        "department_ids": [str(profile_route_actor.department_id)],
                        "email_ids": [str(resources.email_id)],
                        "role_ids": [str(resources.role_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "profile_id": payload["results"][0]["profile_id"],
            "name": resources.name,
        }
