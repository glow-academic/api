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
    dept_id = uuid4()
    monkeypatch.setattr(
        resolvers,
        "search_departments",
        _async_result(([dept_id], 1)),
    )
    monkeypatch.setattr(
        resolvers,
        "get_department_resources",
        _async_result([_ns(id=dept_id, name="Ops")]),
    )

    result = await resolvers.resolve_departments_for_sync(object(), object())

    assert result == [
        resolvers.DepartmentForSync(department_id=dept_id, department_name="Ops")
    ]


@pytest.mark.asyncio
async def test_resolve_auths_for_department_follows_department_setting_auth_chain(
    monkeypatch,
):
    department_id = uuid4()
    setting_id = uuid4()
    auth_id = uuid4()
    monkeypatch.setattr(
        resolvers,
        "get_department_artifacts",
        _async_result([_ns(settings_ids=[setting_id])]),
    )
    monkeypatch.setattr(
        resolvers,
        "get_setting_artifacts",
        _async_result([_ns(auth_ids=[auth_id])]),
    )
    monkeypatch.setattr(
        resolvers,
        "get_auth_resources",
        _async_result(
            [_ns(id=auth_id, slug="sso", protocol="oidc", name="SSO", active=True)]
        ),
    )

    result = await resolvers.resolve_auths_for_department(
        object(), object(), department_id
    )

    assert result == [
        resolvers.AuthForSync(id=auth_id, slug="sso", provider_id="oidc", name="SSO")
    ]


@pytest.mark.asyncio
async def test_resolve_auths_for_realm_filters_out_department_scoped_settings(
    monkeypatch,
):
    dept_id = uuid4()
    dept_setting_id = uuid4()
    realm_setting_id = uuid4()
    setting_artifact_id = uuid4()
    auth_id = uuid4()

    monkeypatch.setattr(resolvers, "search_departments", _async_result(([dept_id], 1)))
    monkeypatch.setattr(
        resolvers,
        "get_department_artifacts",
        _async_result([_ns(id=dept_id, settings_ids=[dept_setting_id])]),
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
            [
                _ns(
                    id=setting_artifact_id,
                    setting_ids=[dept_setting_id, realm_setting_id],
                    auth_ids=[auth_id],
                )
            ]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_auth_resources",
        _async_result(
            [_ns(id=auth_id, slug="realm", protocol="oidc", name="Realm", active=True)]
        ),
    )

    result = await resolvers.resolve_auths_for_realm(object(), object())

    assert result == [
        resolvers.AuthForSync(
            id=auth_id, slug="realm", provider_id="oidc", name="Realm"
        )
    ]


@pytest.mark.asyncio
async def test_resolve_setting_profiles_for_idp_builds_department_and_default_scope(
    monkeypatch,
):
    dept_id = uuid4()
    dept_setting_id = uuid4()
    profile_id = uuid4()
    setting_artifact_id = uuid4()

    monkeypatch.setattr(resolvers, "search_departments", _async_result(([dept_id], 1)))
    monkeypatch.setattr(
        resolvers,
        "get_department_resources",
        _async_result([_ns(id=dept_id, setting_ids=[dept_setting_id])]),
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
            [
                _ns(
                    id=setting_artifact_id,
                    profile_ids=[profile_id],
                    setting_ids=[dept_setting_id],
                )
            ]
        ),
    )
    monkeypatch.setattr(
        resolvers,
        "get_profiles",
        _async_result([_ns(id=profile_id, name="Ada", role="admin", active=True)]),
    )

    result = await resolvers.resolve_setting_profiles_for_idp(object(), object())

    assert result == [
        resolvers.SettingProfileForIdp(
            profile_id=profile_id,
            profile_name="Ada",
            role="admin",
            setting_id=setting_artifact_id,
            department_id=dept_id,
        )
    ]


@pytest.mark.asyncio
async def test_resolve_auth_items_prefers_department_specific_values(monkeypatch):
    auth_id = uuid4()
    department_id = uuid4()
    item_encrypted_id = uuid4()
    item_plain_id = uuid4()
    dept_setting_id = uuid4()
    default_setting_id = uuid4()
    setting_artifact_id = uuid4()
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
    monkeypatch.setattr(
        resolvers,
        "get_department_resources",
        _async_result([_ns(setting_ids=[dept_setting_id])]),
    )
    monkeypatch.setattr(
        resolvers,
        "search_departments",
        _async_result(([department_id], 1)),
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
            [
                _ns(
                    setting_ids=[dept_setting_id],
                    auth_item_keys_ids=[dept_aik_id],
                    auth_item_value_ids=[dept_aiv_id],
                ),
                _ns(
                    setting_ids=[default_setting_id],
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
