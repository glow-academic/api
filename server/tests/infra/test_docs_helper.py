"""Tests for shared docs helper utilities."""

from types import ModuleType

import pytest

from app.infra.docs_helper import (
    ArtifactDocsConfig,
    PageMetadataConfig,
    ResourceDocsConfig,
    _extract_linked_resources,
    _parse_docstring,
    build_artifact_docs_static,
    build_resource_docs_static,
    compute_docs_metadata,
    extract_business_logic,
    get_foreign_keys,
    get_junction_tables,
    get_table_columns,
)

pytestmark = pytest.mark.asyncio


def _sample_permission() -> None:
    """Primary rule summary.

    - first rule
    - second rule
    """


def _plain_permission() -> None:
    """Plain summary only."""


class TestPageMetadata:
    async def test_compute_docs_metadata_uses_entity_name_for_detail(self):
        result = compute_docs_metadata(
            PageMetadataConfig(
                list_title="Profiles",
                list_description="All profiles",
                detail_title="Details",
                detail_description="Profile details",
                new_title="New Profile",
                new_description="Create one",
            ),
            entity_name="Alice",
        )

        assert result.list.title == "Profiles"
        assert result.detail.title == "Alice Details"
        assert result.new.title == "New Profile"


class TestSchemaDiscovery:
    async def test_get_table_columns_reads_real_columns(self, conn):
        columns = await get_table_columns(conn, "messages_entry")
        column_names = {column["name"] for column in columns}

        assert "id" in column_names
        assert "run_id" in column_names
        assert "role" in column_names

    async def test_get_junction_tables_finds_profile_junctions(self, conn):
        junctions = await get_junction_tables(conn, "profile")
        names = {junction["name"] for junction in junctions}

        assert "profile_departments_junction" in names
        assert "profile_emails_junction" in names

    async def test_get_foreign_keys_reads_real_fk_relationships(self, conn):
        foreign_keys = await get_foreign_keys(conn, "profile_%")

        assert any(
            fk["table"] == "profile_departments_junction"
            and fk["references"] == "departments_resource"
            for fk in foreign_keys
        )


class TestBusinessLogicExtraction:
    async def test_parse_docstring_extracts_description_and_rules(self):
        parsed = _parse_docstring(_sample_permission.__doc__)

        assert parsed == {
            "description": "Primary rule summary.",
            "rules": ["first rule", "second rule"],
        }

    async def test_extract_business_logic_uses_module_functions(self):
        module = ModuleType("fake_permissions")
        module.sample = _sample_permission
        module.plain = _plain_permission

        result = extract_business_logic(module, ["sample", "plain", "missing"])

        assert result["sample"]["description"] == "Primary rule summary."
        assert result["sample"]["rules"] == ["first rule", "second rule"]
        assert "def _sample_permission" in result["sample"]["source"]
        assert result["plain"]["rules"] == []

    async def test_extract_linked_resources_parses_junction_names(self):
        assert _extract_linked_resources(
            [
                {"name": "profile_departments_junction"},
                {"name": "profile_emails_junction"},
                {"name": "other_table"},
            ],
            "profile",
        ) == ["departments", "emails"]


class TestStaticBuilders:
    async def test_build_artifact_docs_static_includes_sections(self):
        module = ModuleType("fake_permissions")
        module.sample = _sample_permission

        docs = build_artifact_docs_static(
            ArtifactDocsConfig(
                name="profile",
                plural_name="profiles",
                table_name="profile_artifact",
                permissions_module=module,
                permission_functions=["sample"],
                api_routing={"route": "/profiles"},
                resources_info=[{"name": "emails"}],
                glow_context={"ui": "artifact"},
                extra_sections={"notes": ["one"]},
            )
        )

        assert docs["name"] == "profiles"
        assert docs["database"]["table"] == "profile_artifact"
        assert docs["business_logic"]["sample"]["rules"] == [
            "first rule",
            "second rule",
        ]
        assert docs["api_routing"] == {"route": "/profiles"}
        assert docs["resources"] == {"available": [{"name": "emails"}]}
        assert docs["notes"] == ["one"]

    async def test_build_resource_docs_static_includes_resource_fields(self):
        docs = build_resource_docs_static(
            ResourceDocsConfig(
                name="names",
                table_name="names_resource",
                description="Name resources",
                glow_context={"ui": "resource"},
                used_by_artifacts=["persona", "profile"],
                extra_sections={"examples": ["Alice"]},
            )
        )

        assert docs == {
            "name": "names",
            "type": "resource",
            "description": "Name resources",
            "database": {"table": "names_resource"},
            "used_by_artifacts": ["persona", "profile"],
            "glow_context": {"ui": "resource"},
            "examples": ["Alice"],
        }
