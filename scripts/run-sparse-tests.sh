#!/bin/bash
# Run tests only for changed infra/ and tools/ files (beta fast path).
#
# Maps changed source files to their test counterparts:
#   core/app/infra/{domain}/{name}.py → core/tests/infra/{domain}/test_{name}.py
#   core/app/tools/{domain}/{name}.py → core/tests/tools/{domain}/test_{name}.py
#   core/app/utils/{name}.py → core/tests/utils/test_{name}.py
#
# Falls back to skip if no matching tests found.

set -e

BASE_BRANCH="${1:-main}"

# Get changed .py files in testable directories
CHANGED=$(git diff --name-only "origin/$BASE_BRANCH"...HEAD -- 'core/app/infra/**/*.py' 'core/app/tools/**/*.py' 'core/app/utils/**/*.py' 2>/dev/null || \
          git diff --name-only HEAD~1 -- 'core/app/infra/**/*.py' 'core/app/tools/**/*.py' 'core/app/utils/**/*.py' 2>/dev/null || echo "")

if [ -z "$CHANGED" ]; then
  echo "No testable source changes detected (infra/tools/utils) — skipping sparse tests"
  exit 0
fi

echo "Changed source files:"
echo "$CHANGED" | sed 's/^/  /'

# Map source files to test files
# core/app/infra/agent/types.py → core/tests/infra/agent/test_types.py
TEST_FILES=""
for src in $CHANGED; do
  base=$(basename "$src")
  # Skip __init__.py
  [ "$base" = "__init__.py" ] && continue

  name="${base%.py}"
  # Replace core/app/ with core/tests/ and prepend test_ to filename
  test=$(echo "$src" | sed 's|core/app/|core/tests/|' | sed "s|${base}|test_${name}.py|")

  if [ -f "$test" ] && ! echo "$TEST_FILES" | grep -q "$test"; then
    TEST_FILES="$TEST_FILES $test"
  fi
done

if [ -z "$TEST_FILES" ]; then
  echo "No matching test files found for changed sources — skipping"
  exit 0
fi

COUNT=$(echo "$TEST_FILES" | wc -w | tr -d ' ')
echo ""
echo "Running $COUNT sparse test file(s):"
echo "$TEST_FILES" | tr ' ' '\n' | sed 's/^/  /'
echo ""

PYTHONPATH=core python -m pytest $TEST_FILES -v --tb=short
