#!/usr/bin/env bash
#
# Concatenates database/schema/ files back into a single loadable SQL file.
#
# Load order:
#   1. extensions.sql
#   2. enums/*.sql
#   3. tables/ (artifacts, entries, resources, junctions, connections)
#   4. indexes/ (same subfolder structure as tables/)
#   5. foreign_keys/ (same subfolder structure)
#   6. views/*.sql (materialized views — pure CREATE ... WITH NO DATA)
#   7. indexes/views/*.sql (MV indexes)
#
# Usage:
#   bash database/scripts/concat_schema.sh [output_path]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$SCRIPT_DIR")"
SCHEMA_DIR="$DB_DIR/schema"
OUTPUT="${1:-$DB_DIR/schema.sql}"

if [ ! -d "$SCHEMA_DIR" ]; then
    echo "Error: $SCHEMA_DIR not found" >&2
    exit 1
fi

TABLE_SUBFOLDERS="artifacts entries resources junctions connections"

{
    cat "$SCHEMA_DIR/extensions.sql"

    # Enums
    for f in $(find "$SCHEMA_DIR/enums" -name '*.sql' | sort); do
        echo ""
        cat "$f"
    done

    # Tables (with inline constraints)
    for subfolder in $TABLE_SUBFOLDERS; do
        dir="$SCHEMA_DIR/tables/$subfolder"
        if [ -d "$dir" ]; then
            for f in $(find "$dir" -name '*.sql' | sort); do
                echo ""
                cat "$f"
            done
        fi
    done

    # Indexes (parallel structure, excluding views/)
    for subfolder in $TABLE_SUBFOLDERS; do
        dir="$SCHEMA_DIR/indexes/$subfolder"
        if [ -d "$dir" ]; then
            for f in $(find "$dir" -name '*.sql' | sort); do
                echo ""
                cat "$f"
            done
        fi
    done

    # Foreign keys
    for subfolder in $TABLE_SUBFOLDERS; do
        dir="$SCHEMA_DIR/foreign_keys/$subfolder"
        if [ -d "$dir" ]; then
            for f in $(find "$dir" -name '*.sql' | sort); do
                echo ""
                cat "$f"
            done
        fi
    done

    # Set search_path for views (they use unqualified table names)
    echo ""
    echo "SET search_path = public;"

    # Materialized views (pure CREATE ... WITH NO DATA)
    if [ -d "$SCHEMA_DIR/views" ]; then
        for f in $(find "$SCHEMA_DIR/views" -name '*.sql' | sort); do
            echo ""
            cat "$f"
        done
    fi

    # MV indexes
    if [ -d "$SCHEMA_DIR/indexes/views" ]; then
        for f in $(find "$SCHEMA_DIR/indexes/views" -name '*.sql' | sort); do
            echo ""
            cat "$f"
        done
    fi
} > "$OUTPUT"

echo "Concatenated schema files → $OUTPUT ($(wc -c < "$OUTPUT" | tr -d ' ') bytes)"
