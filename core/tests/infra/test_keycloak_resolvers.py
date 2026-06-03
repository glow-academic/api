from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.infra.identity import keycloak_resolvers as resolvers


def _ns(**kwargs):
    class Obj:
        pass

    obj = Obj()
    for key, value in kwargs.items():
        setattr(obj, key, value)
    return obj


def _async_result(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


@pytest.mark.asyncio
async def test_resolve_departments_for_sync_uses_search_and_resource_fetch(monkeypatch):
    # Multi-hop: search_departments (artifact ids) -> get_department_artifacts
    # (artifact -> resource id via self-link junction) -> get_department_resources.
    dept_artifact_id = uuid4()
    dept_resource_id = uuid4()
    monkeypatch.setattr(
        resolvers,
        "search_departments",
        _async_result(([dept_artifact_id], 1)),
    )
    monkeypatch.setattr(
        resolvers,
        "get_department_artifacts",
        _async_result([_ns(id=dept_artifact_id, department_ids=[dept_resource_id])]),
    )
    monkeypatch.setattr(
        resolvers,
        "get_department_resources",
        _async_result([_ns(id=dept_resource_id, name="Ops")]),
    )

    result = await resolvers.resolve_departments_for_sync(object(), object())

    # department_id is mapped back to the artifact id via resource->artifact map.
    assert result == [
        resolvers.DepartmentForSync(
            department_id=dept_artifact_id, department_name="Ops"
        )
    ]


@pytest.mark.asyncio
async def test_resolve_auths_for_department_follows_department_setting_auth_chain(
    monkeypatch,
):
    # Multi-hop chain: department_artifact -> dept resource id -> search_settings
    # -> setting artifacts filtered by department_ids -> setting_logins_junction
    # -> logins_resource (login_type='auth') -> auth resources.
    department_artifact_id = uuid4()
    dept_resource_id = uuid4()
    setting_artifact_id = uuid4()
    login_id = uuid4()
    auth_id = uuid4()
    monkeypatch.setattr(
        resolvers,
        "get_department_artifacts",
        _async_result([_ns(id=department_artifact_id, department_ids=[dept_resource_id])]),
    )
    monkeypatch.setattr(
        resolvers,
        "search_settings",
        _async_result(([setting_artifact_id], 1)),
    )
    monkeypatch.setattr(
        resolvers,
        "get_setting_artifacts",
        _async_result(
            [_ns(department_ids=[dept_resource_id], logins_ids=[login_id])]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_logins",
        _async_result([_ns(id=login_id, auth_id=auth_id, login_type="auth")]),
    )
    monkeypatch.setattr(
        resolvers,
        "get_auth_resources",
        _async_result(
            [_ns(id=auth_id, slug="sso", protocol="oidc", name="SSO", active=True)]
        ),
    )

    result = await resolvers.resolve_auths_for_department(
        object(), object(), department_artifact_id
    )

    assert result == [
        resolvers.AuthForSync(id=auth_id, slug="sso", provider_id="oidc", name="SSO")
    ]


@pytest.mark.asyncio
async def test_resolve_auths_for_realm_filters_out_department_scoped_settings(
    monkeypatch,
):
    # Realm-level resolution keeps only settings with no department_ids, then
    # follows setting_logins_junction -> logins (login_type='auth') -> auths.
    # A dept-scoped setting (with department_ids) and its login must be skipped.
    dept_resource_id = uuid4()
    dept_setting_artifact_id = uuid4()
    realm_setting_artifact_id = uuid4()
    dept_login_id = uuid4()
    realm_login_id = uuid4()
    realm_auth_id = uuid4()

    monkeypatch.setattr(
        resolvers,
        "search_settings",
        _async_result(([dept_setting_artifact_id, realm_setting_artifact_id], 2)),
    )
    monkeypatch.setattr(
        resolvers,
        "get_setting_artifacts",
        _async_result(
            [
                # Department-scoped: has department_ids -> excluded from realm.
                _ns(
                    id=dept_setting_artifact_id,
                    department_ids=[dept_resource_id],
                    logins_ids=[dept_login_id],
                ),
                # Realm-level: no department_ids -> included.
                _ns(
                    id=realm_setting_artifact_id,
                    department_ids=[],
                    logins_ids=[realm_login_id],
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_logins",
        _async_result(
            [_ns(id=realm_login_id, auth_id=realm_auth_id, login_type="auth")]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_auth_resources",
        _async_result(
            [
                _ns(
                    id=realm_auth_id,
                    slug="realm",
                    protocol="oidc",
                    name="Realm",
                    active=True,
                )
            ]
        ),
    )

    result = await resolvers.resolve_auths_for_realm(object(), object())

    assert result == [
        resolvers.AuthForSync(
            id=realm_auth_id, slug="realm", provider_id="oidc", name="Realm"
        )
    ]


@pytest.mark.asyncio
async def test_resolve_setting_profiles_for_idp_builds_department_and_default_scope(
    monkeypatch,
):
    # Multi-hop: search_departments -> dept artifacts (resource id) -> dept
    # resources (setting_ids identify dept-scoped settings) ; then settings ->
    # setting_logins_junction -> logins (login_type='profile' -> profile resource
    # id) ; profile resource ids are mapped back to profile artifact ids via the
    # profile self-link junction. A setting whose setting resource id is in a
    # department's setting_ids is department-scoped; otherwise it is default.
    # NOTE: role is no longer carried by profiles_resource, so role is always None.
    dept_artifact_id = uuid4()
    dept_resource_id = uuid4()
    dept_setting_resource_id = uuid4()
    default_setting_resource_id = uuid4()
    dept_setting_artifact_id = uuid4()
    default_setting_artifact_id = uuid4()
    dept_login_id = uuid4()
    default_login_id = uuid4()
    dept_profile_resource_id = uuid4()
    default_profile_resource_id = uuid4()
    dept_profile_artifact_id = uuid4()
    default_profile_artifact_id = uuid4()

    monkeypatch.setattr(
        resolvers, "search_departments", _async_result(([dept_artifact_id], 1))
    )
    monkeypatch.setattr(
        resolvers,
        "get_department_artifacts",
        _async_result([_ns(id=dept_artifact_id, department_ids=[dept_resource_id])]),
    )
    monkeypatch.setattr(
        resolvers,
        "get_department_resources",
        _async_result(
            [_ns(id=dept_resource_id, setting_ids=[dept_setting_resource_id])]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "search_settings",
        _async_result(
            ([dept_setting_artifact_id, default_setting_artifact_id], 2)
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_setting_artifacts",
        _async_result(
            [
                _ns(
                    id=dept_setting_artifact_id,
                    logins_ids=[dept_login_id],
                    setting_ids=[dept_setting_resource_id],
                ),
                _ns(
                    id=default_setting_artifact_id,
                    logins_ids=[default_login_id],
                    setting_ids=[default_setting_resource_id],
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_logins",
        _async_result(
            [
                _ns(
                    id=dept_login_id,
                    profile_id=dept_profile_resource_id,
                    login_type="profile",
                ),
                _ns(
                    id=default_login_id,
                    profile_id=default_profile_resource_id,
                    login_type="profile",
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "search_profiles",
        _async_result(
            ([dept_profile_artifact_id, default_profile_artifact_id], 2)
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_profile_artifacts",
        _async_result(
            [
                _ns(
                    id=dept_profile_artifact_id,
                    profile_ids=[dept_profile_resource_id],
                ),
                _ns(
                    id=default_profile_artifact_id,
                    profile_ids=[default_profile_resource_id],
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_profiles",
        _async_result(
            [
                _ns(id=dept_profile_resource_id, name="Ada", active=True),
                _ns(id=default_profile_resource_id, name="Grace", active=True),
            ]
        ),
    )

    result = await resolvers.resolve_setting_profiles_for_idp(object(), object())

    assert resolvers.SettingProfileForIdp(
        profile_id=dept_profile_artifact_id,
        profile_name="Ada",
        role=None,
        setting_id=dept_setting_artifact_id,
        department_id=dept_artifact_id,
    ) in result
    assert resolvers.SettingProfileForIdp(
        profile_id=default_profile_artifact_id,
        profile_name="Grace",
        role=None,
        setting_id=default_setting_artifact_id,
        department_id=None,
    ) in result
    assert len(result) == 2


@pytest.mark.asyncio
async def test_resolve_auth_items_prefers_department_specific_values(monkeypatch):
    auth_id = uuid4()
    department_id = uuid4()
    dept_resource_id = uuid4()
    item_encrypted_id = uuid4()
    item_plain_id = uuid4()
    dept_setting_artifact_id = uuid4()
    default_setting_artifact_id = uuid4()
    key_id = uuid4()
    dept_aik_id = uuid4()
    default_aik_id = uuid4()
    dept_aiv_id = uuid4()
    default_aiv_id = uuid4()
    default_created_at = datetime(2026, 1, 1, tzinfo=UTC)
    dept_created_at = datetime(2026, 1, 2, tzinfo=UTC)

    monkeypatch.setattr(
        resolvers,
        "get_auth_artifacts",
        _async_result([_ns(item_ids=[item_encrypted_id, item_plain_id])]),
    )
    monkeypatch.setattr(
        resolvers,
        "get_items",
        _async_result(
            [
                _ns(id=item_encrypted_id, name="client_secret", encrypted=True),
                _ns(id=item_plain_id, name="issuer", encrypted=False),
            ]
        ),
    )
    # Department artifact -> resource id; settings are categorized dept vs default
    # by whether their department_ids contains this resource id.
    monkeypatch.setattr(
        resolvers,
        "get_department_artifacts",
        _async_result([_ns(id=department_id, department_ids=[dept_resource_id])]),
    )
    monkeypatch.setattr(
        resolvers,
        "search_settings",
        _async_result(
            ([dept_setting_artifact_id, default_setting_artifact_id], 2)
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_setting_artifacts",
        _async_result(
            [
                _ns(
                    id=dept_setting_artifact_id,
                    department_ids=[dept_resource_id],
                    auth_item_keys_ids=[dept_aik_id],
                    auth_item_value_ids=[dept_aiv_id],
                ),
                _ns(
                    id=default_setting_artifact_id,
                    department_ids=[],
                    auth_item_keys_ids=[default_aik_id],
                    auth_item_value_ids=[default_aiv_id],
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_auth_item_keys",
        _async_result(
            [
                _ns(
                    id=default_aik_id,
                    auth_id=auth_id,
                    item_id=item_encrypted_id,
                    key_id=key_id,
                    active=True,
                    created_at=default_created_at,
                ),
                _ns(
                    id=dept_aik_id,
                    auth_id=auth_id,
                    item_id=item_encrypted_id,
                    key_id=key_id,
                    active=True,
                    created_at=dept_created_at,
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_auth_item_values",
        _async_result(
            [
                _ns(
                    id=default_aiv_id,
                    auth_id=auth_id,
                    item_id=item_plain_id,
                    value="default-issuer",
                    active=True,
                    created_at=default_created_at,
                ),
                _ns(
                    id=dept_aiv_id,
                    auth_id=auth_id,
                    item_id=item_plain_id,
                    value="dept-issuer",
                    active=True,
                    created_at=dept_created_at,
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_keys",
        _async_result([_ns(id=key_id, key="encrypted-secret")]),
    )

    result = await resolvers.resolve_auth_items(
        object(), object(), auth_id, department_id
    )
    by_name = {item.name: item for item in result}

    assert by_name["client_secret"].value == "encrypted-secret"
    assert by_name["client_secret"].encrypted is True
    assert by_name["issuer"].value == "dept-issuer"
    assert by_name["issuer"].encrypted is False
