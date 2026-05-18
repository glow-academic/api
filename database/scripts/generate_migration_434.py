#!/usr/bin/env python3
"""Generate migration 434 SQL with HTML content from template files."""

import os
import uuid

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
MIGRATE_DIR = os.path.join(os.path.dirname(__file__), "..", "migrate")

# Template texts_entry IDs (template name -> texts_entry.id)
TEMPLATE_TEXTS_ENTRY = {
    "homework": "019c29d6-003a-7f3d-9c60-a6c537f708ce",
    "lab": "019c29d6-003a-740e-8854-4d9ee26d34a6",
    "lecture": "019c29d6-003b-7026-b46a-5def99ec275a",
    "midterm": "019c29d6-003a-731f-b918-64b6c99d0464",
    "project": "019c29d6-003a-7541-984b-5374263aa03b",
    "quiz": "019c29d6-003b-71b1-bfa5-69ef5f636751",
    "syllabus": "019c29d6-003a-7647-aa7f-b9baebd83bf3",
}

# Policy template to delete
POLICY_TEMPLATE_ID = "019bc71d-3ebb-7169-ba1c-335ec67c093c"
POLICY_TEXTS_ID = "019c29d6-005c-74a5-91f7-f309588e109b"
POLICY_TEXTS_ENTRY_ID = "019c29d6-003a-71f3-acc6-88aa2d7e8f12"

# Scenario RESOURCE IDs (for scenarios_resource.templates_enabled)
TEXT_SCENARIO_RESOURCE_IDS = [
    "019bb25e-e61d-7f22-b0ce-2f8bd6f51c97",  # Happy Scenario
    "019bb25e-e61d-7f0d-8cb0-426ba262f584",  # Confused Scenario
    "019bb25e-e61d-7f2b-90fe-0ddfddd5d737",  # Passive Scenario
    "019bb25e-e61d-7f26-9e97-cc57dff6f2fe",  # Aggressive Scenario
    "019bb25e-e61d-7efa-8819-7dcb0cf829f8",  # General Scenario
]

# Scenario ARTIFACT IDs (for junction tables like scenario_documents_junction, scenario_templates_junction)
VIDEO_SCENARIO_ARTIFACT_IDS = {
    "academic-integrity": "019b3be4-3c3a-7a07-b866-50473cddc11e",
    "ferpa": "019b3be4-3c3a-79d9-8a7c-08f5beebc77f",
    "upset-student": "019b3be4-3c3a-79f1-9490-d4358ed29c92",
}

# FERPA document resource ID (to attach to FERPA scenario)
FERPA_DOCUMENT_ID = "019bb25e-e619-7831-a70a-a7fb065a1999"


def sql_escape(text: str) -> str:
    """Escape text for use in SQL string literals using dollar quoting."""
    # Use dollar quoting to avoid issues with single quotes and backslashes
    # Find a unique tag
    tag = "HTML"
    i = 0
    while f"${tag}$" in text:
        tag = f"HTML{i}"
        i += 1
    return f"${tag}${text}${tag}$"


def read_html(filename: str) -> str:
    path = os.path.join(UPLOADS_DIR, filename)
    with open(path) as f:
        return f.read()


def generate():
    lines = []
    lines.append("-- Migration 434: Template and scenario configuration changes")
    lines.append(
        "-- 1. Update texts_entry content for 7 existing templates (remove Jinja, fill in content)"
    )
    lines.append("-- 2. Delete the policy template chain")
    lines.append("-- 3. Set templates_enabled = true on 5 text-based scenarios")
    lines.append("-- 4. Attach FERPA document to FERPA Training Scenario")
    lines.append(
        "-- 5. Create 2 new templates for Academic Integrity and Upset Student scenarios"
    )
    lines.append("-- 6. Attach new templates to their respective video scenarios")
    lines.append("")
    lines.append("BEGIN;")
    lines.append("")

    # --- 1. Update existing template HTML content ---
    lines.append("-- ============================================================")
    lines.append("-- 1. Update texts_entry content for 7 templates")
    lines.append("-- ============================================================")
    for name, entry_id in TEMPLATE_TEXTS_ENTRY.items():
        html = read_html(f"template-{name}.html")
        escaped = sql_escape(html)
        lines.append(
            f"UPDATE public.texts_entry SET content = {escaped} WHERE id = '{entry_id}';"
        )
        lines.append("")

    # --- 2. Delete policy template chain ---
    lines.append("-- ============================================================")
    lines.append("-- 2. Delete policy template chain")
    lines.append("-- ============================================================")
    lines.append("-- Remove any scenario_templates_junction rows referencing policy")
    lines.append(
        f"DELETE FROM public.scenario_templates_junction WHERE template_id = '{POLICY_TEMPLATE_ID}';"
    )
    lines.append("-- Remove texts_texts_connection")
    lines.append(
        f"DELETE FROM public.texts_texts_connection WHERE texts_id = '{POLICY_TEXTS_ID}';"
    )
    lines.append("-- Remove texts_entry")
    lines.append(
        f"DELETE FROM public.texts_entry WHERE id = '{POLICY_TEXTS_ENTRY_ID}';"
    )
    lines.append("-- Remove texts_resource")
    lines.append(f"DELETE FROM public.texts_resource WHERE id = '{POLICY_TEXTS_ID}';")
    lines.append("-- Remove templates_resource")
    lines.append(
        f"DELETE FROM public.templates_resource WHERE id = '{POLICY_TEMPLATE_ID}';"
    )
    lines.append("")

    # --- 3. Enable templates on text-based scenarios ---
    lines.append("-- ============================================================")
    lines.append("-- 3. Set templates_enabled = true on 5 text-based scenarios")
    lines.append("-- ============================================================")
    ids_list = ", ".join(f"'{sid}'" for sid in TEXT_SCENARIO_RESOURCE_IDS)
    lines.append(
        f"UPDATE public.scenarios_resource SET templates_enabled = true WHERE id IN ({ids_list});"
    )
    lines.append("")

    # --- 4. Attach FERPA document to FERPA scenario ---
    lines.append("-- ============================================================")
    lines.append("-- 4. Attach FERPA document to FERPA Training Scenario")
    lines.append("-- ============================================================")
    ferpa_scenario_id = VIDEO_SCENARIO_ARTIFACT_IDS["ferpa"]
    lines.append(
        "INSERT INTO public.scenario_documents_junction (scenario_id, document_id, active, created_at, generated, mcp)"
    )
    lines.append(
        f"VALUES ('{ferpa_scenario_id}', '{FERPA_DOCUMENT_ID}', true, NOW(), false, false)"
    )
    lines.append("ON CONFLICT (scenario_id, document_id) DO NOTHING;")
    lines.append("")

    # --- 5. Create 2 new templates for video scenarios ---
    lines.append("-- ============================================================")
    lines.append("-- 5. Create new templates for Academic Integrity and Upset Student")
    lines.append("-- ============================================================")

    new_templates = {
        "academic-integrity": {
            "template_id": str(uuid.uuid4()),
            "texts_resource_id": str(uuid.uuid4()),
            "texts_entry_id": str(uuid.uuid4()),
            "name": "Template HTML: Template: Academic Integrity Policy",
            "description": "Academic integrity policy document for video-based training scenarios",
            "html_file": "template-academic-integrity-policy.html",
            "scenario_artifact_id": VIDEO_SCENARIO_ARTIFACT_IDS["academic-integrity"],
        },
        "upset-student": {
            "template_id": str(uuid.uuid4()),
            "texts_resource_id": str(uuid.uuid4()),
            "texts_entry_id": str(uuid.uuid4()),
            "name": "Template HTML: Template: Upset Student Policy",
            "description": "Distressed and disruptive student response policy for video-based training scenarios",
            "html_file": "template-upset-student-policy.html",
            "scenario_artifact_id": VIDEO_SCENARIO_ARTIFACT_IDS["upset-student"],
        },
    }

    for key, tmpl in new_templates.items():
        html = read_html(tmpl["html_file"])
        escaped = sql_escape(html)

        lines.append(f"-- Template: {tmpl['name']}")
        lines.append("-- texts_entry")
        lines.append(
            "INSERT INTO public.texts_entry (id, content, created_at, updated_at, active, generated, mcp)"
        )
        lines.append(
            f"VALUES ('{tmpl['texts_entry_id']}', {escaped}, NOW(), NOW(), true, false, false);"
        )
        lines.append("-- texts_resource")
        lines.append(
            "INSERT INTO public.texts_resource (id, created_at, active, generated, mcp)"
        )
        lines.append(
            f"VALUES ('{tmpl['texts_resource_id']}', NOW(), true, false, false);"
        )
        lines.append("-- texts_texts_connection")
        lines.append(
            "INSERT INTO public.texts_texts_connection (texts_id, text_id, active, created_at, updated_at)"
        )
        lines.append(
            f"VALUES ('{tmpl['texts_resource_id']}', '{tmpl['texts_entry_id']}', true, NOW(), NOW());"
        )
        lines.append("-- templates_resource")
        lines.append(
            "INSERT INTO public.templates_resource (id, name, description, created_at, active, generated, mcp, texts_id)"
        )
        lines.append(
            f"VALUES ('{tmpl['template_id']}', '{tmpl['name']}', '{tmpl['description']}', NOW(), true, false, false, '{tmpl['texts_resource_id']}');"
        )
        lines.append("")

    # --- 6. Attach new templates to video scenarios ---
    lines.append("-- ============================================================")
    lines.append("-- 6. Attach new templates to video scenarios")
    lines.append("-- ============================================================")
    for key, tmpl in new_templates.items():
        lines.append(
            "INSERT INTO public.scenario_templates_junction (scenario_id, template_id, active, created_at, generated, mcp)"
        )
        lines.append(
            f"VALUES ('{tmpl['scenario_artifact_id']}', '{tmpl['template_id']}', true, NOW(), false, false)"
        )
        lines.append("ON CONFLICT (scenario_id, template_id) DO NOTHING;")
        lines.append("")

    lines.append("COMMIT;")
    lines.append("")

    # Write the migration file
    output_path = os.path.join(
        MIGRATE_DIR, "434_template_and_scenario_configuration.sql"
    )
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Generated migration: {output_path}")
    print("New template IDs:")
    for key, tmpl in new_templates.items():
        print(
            f"  {key}: template={tmpl['template_id']}, texts_resource={tmpl['texts_resource_id']}, texts_entry={tmpl['texts_entry_id']}"
        )


if __name__ == "__main__":
    generate()
