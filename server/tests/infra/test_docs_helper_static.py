"""Tests for static docs helper builders."""

from types import ModuleType

from app.infra.docs_helper import (
    ArtifactDocsConfig,
    ResourceDocsConfig,
    _extract_linked_resources,
    build_artifact_docs_static,
    build_resource_docs_static,
)


def _module_with_permission() -> ModuleType:
    module = ModuleType("permission_module")

    def can_view() -> bool:
        """Can view the entity.

        - Must belong to department
        - Must have active membership
        """
        return True

    module.can_view = can_view  # type: ignore[attr-defined]
    return module


def test_extract_linked_resources_parses_matching_junction_names():
    result = _extract_linked_resources(
        [
            {"name": "persona_names_junction"},
            {"name": "persona_roles_junction"},
            {"name": "other_table"},
        ],
        "persona",
    )

    assert result == ["names", "roles"]


def test_build_artifact_docs_static_includes_business_logic_and_sections():
    docs = build_artifact_docs_static(
        ArtifactDocsConfig(
            name="persona",
            plural_name="personas",
            table_name="persona_artifact",
            permissions_module=_module_with_permission(),
            permission_functions=["can_view"],
            api_routing={"list": "/v5/persona/search"},
            resources_info=[{"name": "roles"}],
            glow_context={"owner": "profile"},
            extra_sections={"notes": ["one"]},
        )
    )

    assert docs["name"] == "personas"
    assert docs["database"] == {"table": "persona_artifact"}
    assert docs["api_routing"]["list"] == "/v5/persona/search"
    assert docs["business_logic"]["can_view"]["description"] == "Can view the entity."
    assert docs["resources"]["available"] == [{"name": "roles"}]
    assert docs["notes"] == ["one"]


def test_build_resource_docs_static_omits_empty_optional_sections():
    docs = build_resource_docs_static(
        ResourceDocsConfig(
            name="names",
            description="Human names",
            table_name="names_resource",
        )
    )

    assert docs == {
        "name": "names",
        "type": "resource",
        "description": "Human names",
        "database": {"table": "names_resource"},
    }
