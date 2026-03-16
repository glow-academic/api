"""Root GLOW documentation."""

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/docs", tags=["docs"])


def get_glow_docs() -> dict[str, Any]:
    """Get general GLOW documentation.

    Returns:
        Dictionary containing general information about GLOW, its architecture,
        concepts, and patterns.
    """
    return {
        "name": "GLOW",
        "description": "GLOW is an educational platform for scenario-based learning and AI-powered practice simulations.",
        "architecture": {
            "overview": "GLOW follows a DHH-style architecture with PostgreSQL functions, composite types, and direct SQL execution.",
            "principles": [
                "1 SQL file per route - All SQL logic in separate .sql files",
                "PostgreSQL functions with RETURNS TABLE - Type-safe function-based queries",
                "Composite types instead of JSONB - Strong typing for nested structures",
                "Auto-generated types - Pydantic models generated from SQL introspection",
                "No abstraction layers - Routes directly execute SQL",
                "Client is airgapped - Server actions dominate, client is presentation-only",
            ],
            "database": {
                "type": "PostgreSQL",
                "principles": [
                    "BCNF normalization - Boyce-Codd Normal Form",
                    "No nulls - Minimize null values following Chris Date principles",
                    "Referential integrity - All foreign keys with proper constraints",
                    "Manual migrations - SQL files in database/migrate/ folder",
                ],
            },
            "server": {
                "framework": "FastAPI",
                "pattern": "DHH-style - 1 Python file per route, 1 SQL file per route",
                "type_safety": "Auto-generated Pydantic models from SQL function signatures",
                "caching": "Redis caching with tag-based invalidation",
            },
            "client": {
                "framework": "Next.js",
                "pattern": "Server actions dominate - Next.js server actions for all backend communication",
                "components": "Airgapped UI - Presentation only, no business logic",
                "testing": "No client-side unit testing - All testing happens on server side",
            },
        },
        "concepts": {
            "artifacts": {
                "definition": "Top-level, strong entity tables with singular names",
                "examples": [
                    "personas - AI characters used in scenarios",
                    "scenarios - Practice scenarios for students",
                    "simulations - Interactive simulation sessions",
                    "documents - Document resources",
                    "departments - Organizational departments",
                    "cohorts - Student cohorts",
                    "evals - Evaluation configurations",
                    "rubrics - Grading rubrics",
                    "settings - System settings",
                    "agents - AI agents",
                    "keys - API keys",
                    "models - AI models",
                    "providers - AI providers",
                    "parameters - Configuration parameters",
                    "fields - Custom fields",
                    "profile - User profiles",
                    "auth - Authentication configurations",
                ],
                "operations": [
                    "get - Retrieve a single artifact",
                    "save - Create or update an artifact",
                    "list - List artifacts with filters",
                    "duplicate - Duplicate an existing artifact",
                    "delete - Delete an artifact",
                    "draft - Create or patch a draft (autosave)",
                ],
            },
            "resources": {
                "definition": "Sub-entities or attributes that belong to artifacts, with plural names matching table names",
                "examples": [
                    "names - Name resources for various artifacts",
                    "descriptions - Description resources",
                    "colors - Color resources for UI",
                    "icons - Icon resources for UI",
                    "flags - Boolean flag resources",
                    "examples - Example resources",
                    "fields - Field resources",
                    "departments - Department resources",
                    "instructions - Instruction resources",
                    "content - Content resources",
                    "html - HTML content resources",
                    "hints - Hint resources",
                    "images - Image resources",
                    "videos - Video resources",
                    "objectives - Objective resources",
                    "options - Option resources",
                    "problem_statements - Problem statement resources",
                    "prompts - Prompt resources",
                    "questions - Question resources",
                    "responses - Response resources",
                    "analyses - Analysis resources",
                    "improvements - Improvement resources",
                    "strengths - Strength resources",
                    "feedbacks - Feedback resources",
                    "conversations - Conversation resources",
                    "schemas - Schema resources",
                    "schema_fields - Schema field resources",
                    "schema_field_items - Schema field item resources",
                    "templates - Template resources",
                    "template_array_items - Template array item resources",
                    "template_values - Template value resources",
                    "standard_groups - Standard group resources",
                    "times - Time resources",
                    "points - Point resources",
                    "thresholds - Threshold resources",
                ],
                "operations": [
                    "create - Create a resource (resources are create-only, not full CRUD)"
                ],
                "note": "Resources are typically create-only. They are linked to artifacts via junction tables.",
            },
            "junction_tables": {
                "definition": "Tables that link artifacts to resources or artifacts to other artifacts",
                "pattern": "{artifact}_{resource} where artifact is singular and resource is plural",
                "examples": [
                    "persona_names - Links personas to name resources",
                    "scenario_personas - Links scenarios to personas",
                    "persona_departments - Links personas to departments",
                    "document_fields - Links documents to fields",
                ],
                "note": "Junction tables enable many-to-many relationships between artifacts and resources.",
            },
        },
        "api_patterns": {
            "versioning": "v4 - Current API version",
            "base_path": "/v5/{artifact}",
            "endpoint_structure": {
                "get": "POST /v5/{artifact}/get - Retrieve single artifact",
                "list": "POST /v5/{artifact}/list - List artifacts",
                "duplicate": "POST /v5/{artifact}/duplicate - Duplicate artifact",
                "delete": "POST /v5/{artifact}/delete - Delete artifact",
                "draft": "PATCH /v5/{artifact}/draft - Create or patch draft",
            },
            "resource_endpoints": {
                "create": "POST /v5/resources/{resource} - Create resource"
            },
            "request_response": {
                "request": "Auto-generated Pydantic models from SQL function signatures",
                "response": "Auto-generated Pydantic models from SQL function return types",
                "naming": "{Operation}{Artifact}ApiRequest and {Operation}{Artifact}ApiResponse",
            },
        },
        "sql_patterns": {
            "file_naming": "{operation}_{artifact}_complete.sql",
            "function_naming": "api_{operation}_{artifact}_v4",
            "return_type": "RETURNS TABLE with explicit column types",
            "composite_types": "Use composite types in types schema for nested structures",
            "no_jsonb": "Never use JSONB - use composite types and arrays instead",
            "type_preservation": "Use native PostgreSQL types (uuid, timestamptz) instead of text when possible",
        },
        "testing": {
            "strategy": "No client-side unit testing - All testing happens on server side",
            "unit_tests": "For utils and small utilities (server/tests/unit/)",
            "integration_tests": "For all endpoints (server/tests/integration/v3/)",
            "e2e_tests": "Playwright tests for whole user flows (server/tests/e2e/)",
            "coverage_target": "80% for server",
        },
        "mcp_server": {
            "description": "MCP (Model Context Protocol) server provides tool-based API access to GLOW artifacts and resources",
            "endpoints": {
                "discovery": [
                    "artifacts() - List all artifacts with descriptions",
                    "resources() - List all resources with descriptions",
                    "docs_artifact(name) - Get comprehensive documentation for an artifact",
                    "docs() - Get general GLOW documentation",
                ],
                "schemas": [
                    "payload_artifact(name) - Get payload schema for artifact operations",
                    "payload_resource(name) - Get payload schema for resource operations",
                ],
                "artifact_operations": [
                    "get_artifact(name, payload) - Get an artifact",
                    "list_artifact(name, payload) - List artifacts",
                    "duplicate_artifact(name, payload) - Duplicate an artifact",
                    "delete_artifact(name, payload) - Delete an artifact",
                ],
                "resource_operations": [
                    "create_resource(name, payload) - Create a resource"
                ],
            },
            "documentation": {
                "artifact_docs": "Each artifact has a docs.py file alongside its API routes (e.g., server/app/v5/main/{artifact}/docs.py)",
                "resource_docs": "Each resource has a docs.py file alongside its API routes (e.g., server/app/v5/resources/{resource}/docs.py)",
                "root_docs": "General GLOW documentation in server/app/v5/docs.py",
                "pattern": "MCP server imports artifact/resource docs from API routes and exposes them via docs_artifact() and docs_resource() endpoints",
            },
        },
    }
