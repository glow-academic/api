#!/usr/bin/env python3
"""
Fix qualified column references like profile.id, agent.id, etc. to use _artifact suffix.
"""

import re
from pathlib import Path

# Artifact tables that need qualified column fixes
ARTIFACTS = [
    "agent",
    "auth",
    "chat",
    "cohort",
    "department",
    "document",
    "eval",
    "field",
    "grade",
    "key",
    "message",
    "model",
    "parameter",
    "persona",
    "profile",
    "provider",
    "rubric",
    "run",
    "scenario",
    "setting",
    "simulation",
    "tool",
]

PATTERNS = [
    (r"\b({})\.id\b", r"\1_artifact.id"),
    (r"\bJOIN {}_artifact ON {}\.id\b", r"JOIN \1_artifact ON \1_artifact.id"),
    (r"\bWHERE {}\.id\b", r"WHERE \1_artifact.id"),
    (r"\bAND {}\.id\b", r"AND \1_artifact.id"),
    (r"\bOR {}\.id\b", r"OR \1_artifact.id"),
    (r"\bSELECT {}\.id\b", r"SELECT \1_artifact.id"),
    (r"\bRETURNING {}\.id\b", r"RETURNING \1_artifact.id"),
    (r"\bFROM {}_artifact WHERE {}\.id\b", r"FROM \1_artifact WHERE \1_artifact.id"),
    (r"\bWHERE {}\.id =", r"WHERE \1_artifact.id ="),
    (r"\bWHERE {}\.id IN", r"WHERE \1_artifact.id IN"),
    (r"\bWHERE {}\.id IS", r"WHERE \1_artifact.id IS"),
    (r"\bWHERE {}\.id =", r"WHERE \1_artifact.id ="),
    (r"\bpn\.profile_id = {}\.id\b", r"pn.profile_id = \1_artifact.id"),
    (r"\ban\.auth_id = {}\.id\b", r"an.auth_id = \1_artifact.id"),
    (r"\bmn\.model_id = {}\.id\b", r"mn.model_id = \1_artifact.id"),
    (r"\bmd\.model_id = {}\.id\b", r"md.model_id = \1_artifact.id"),
    (r"\bmf\.model_id = {}\.id\b", r"mf.model_id = \1_artifact.id"),
    (r"\baf\.auth_id = {}\.id\b", r"af.auth_id = \1_artifact.id"),
    (r"\bad\.auth_id = {}\.id\b", r"ad.auth_id = \1_artifact.id"),
    (r"\bap\.auth_id = {}\.id\b", r"ap.auth_id = \1_artifact.id"),
    (r"\bas_j\.auth_id = {}\.id\b", r"as_j.auth_id = \1_artifact.id"),
]


def fix_file(file_path: Path):
    """Fix qualified column references in a file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original = content

        for artifact in ARTIFACTS:
            # Fix JOIN ... ON table.id patterns
            content = re.sub(
                rf"\bJOIN {artifact}_artifact ON {artifact}\.id\b",
                f"JOIN {artifact}_artifact ON {artifact}_artifact.id",
                content,
                flags=re.IGNORECASE,
            )

            # Fix WHERE table.id patterns (but not WHERE table_artifact.id)
            content = re.sub(
                rf"\bWHERE {artifact}\.id\b(?!\s*_)",
                f"WHERE {artifact}_artifact.id",
                content,
                flags=re.IGNORECASE,
            )

            # Fix AND/OR table.id patterns
            content = re.sub(
                rf"\b(AND|OR)\s+{artifact}\.id\b",
                rf"\1 {artifact}_artifact.id",
                content,
                flags=re.IGNORECASE,
            )

            # Fix SELECT table.id patterns
            content = re.sub(
                rf"\bSELECT\s+{artifact}\.id\b",
                f"SELECT {artifact}_artifact.id",
                content,
                flags=re.IGNORECASE,
            )

            # Fix RETURNING table.id patterns
            content = re.sub(
                rf"\bRETURNING\s+{artifact}\.id\b",
                f"RETURNING {artifact}_artifact.id",
                content,
                flags=re.IGNORECASE,
            )

            # Fix qualified references in subqueries
            content = re.sub(
                rf"\b([a-z_]+_id)\s*=\s*{artifact}\.id\b",
                rf"\1 = {artifact}_artifact.id",
                content,
                flags=re.IGNORECASE,
            )

            # Fix specific patterns like pn.profile_id = profile.id
            content = re.sub(
                rf"\b([a-z_]+)\.{artifact}_id\s*=\s*{artifact}\.id\b",
                rf"\1.{artifact}_id = {artifact}_artifact.id",
                content,
                flags=re.IGNORECASE,
            )

        if content != original:
            file_path.write_text(content, encoding="utf-8")
            return True
        return False
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def main():
    sql_dir = Path("server/app/sql")
    sql_files = list(sql_dir.rglob("*.sql"))

    updated = 0
    for sql_file in sql_files:
        if fix_file(sql_file):
            updated += 1

    print(f"Fixed {updated} files")


if __name__ == "__main__":
    main()
