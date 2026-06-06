"""Security regression: the setting response must not leak the raw provider key.

``provider_keys_resource.key`` holds the actual secret provider API key. It is
needed server-side only (``get_provider_keys`` during generation) and must never
be serialized into a caller-reachable response. The setting GET/context response
(``GetSettingApiResponse.provider_keys`` -> ``SettingProviderKeyResource``) is
reachable by any authenticated profile, so the raw key field must not exist on
that response model.

Mirrors the canonical safe pattern: ``keys_catalog`` /
``SettingProviderKeyOption`` only expose identifiers + ``masked_key``, never the
raw secret.
"""

from app.infra.setting.types import (
    GetSettingApiResponse,
    SettingProviderKeyResource,
)


class TestProviderKeySecretNotExposed:
    def test_resource_model_has_no_raw_key_field(self):
        """The response resource must not declare a raw ``key`` field."""
        assert "key" not in SettingProviderKeyResource.model_fields, (
            "SettingProviderKeyResource must not expose the raw provider key "
            "value — it is a secret used only server-side."
        )

    def test_serialized_resource_never_contains_secret(self):
        """A constructed resource never serializes the secret key value.

        Extra/unknown kwargs are ignored by the (default) pydantic model, so even
        if a caller-construction path passed ``key=<secret>`` it can never appear
        in the serialized output.
        """
        secret = "sk-super-secret-provider-key-value"
        resource = SettingProviderKeyResource(
            id=None,
            provider_id=None,
            key_id=None,
            name="My Provider Key",
            description="display only",
            **{"key": secret},  # simulate a stray secret kwarg
        )
        dumped = resource.model_dump(mode="json")
        assert "key" not in dumped
        assert secret not in dumped.values()
        # Identifiers + display metadata are still present.
        assert set(dumped) >= {"id", "provider_id", "key_id", "name", "description"}

    def test_response_model_provider_keys_field_is_secret_free(self):
        """The top-level response model's provider_keys entries carry no secret."""
        assert "provider_keys" in GetSettingApiResponse.model_fields
        # The item type used for the list must be the secret-free resource.
        assert "key" not in SettingProviderKeyResource.model_fields
