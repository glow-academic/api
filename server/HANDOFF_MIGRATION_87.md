# Handoff Brief: Migration 87 — Move is_primary to Resource Tables

## IMPORTANT: Revert Other Agent's SQL/Seed Changes First

A previous agent made changes to SQL query files and seed/module files using the **wrong approach** (separate `profile_primary_departments_junction` / `profile_primary_emails_junction` tables). Those tables **do not exist**. All changes to the files listed below must be **reverted** (`git checkout`) before applying the correct fixes.

```bash
git checkout -- \
  server/app/sql/queries/ \
  database/modules/ \
  database/seeds/ \
  server/app/sql/types.py
```

Then re-run `make sql-compile` to see the original 71 errors and fix them correctly.

## What Changed (Migration 87)

`is_primary` moved from junction tables to resource tables:

- **`departments_resource`** — added `is_primary boolean DEFAULT false NOT NULL`
- **`emails_resource`** — added `is_primary boolean DEFAULT false NOT NULL`
- **`profile_departments_junction`** — dropped `is_primary` column
- **`profile_emails_junction`** — dropped `is_primary` column

There are **NO new junction tables**. No `profile_primary_departments_junction`. No `profile_primary_emails_junction`.

Migration file: `database/migrate/87_primary_department_email_junctions.sql`

## DB State After Migration

```
departments_resource: Organization (is_primary=true), University (is_primary=false)
emails_resource: *@university.edu (is_primary=true), *@organization.com (is_primary=false)
```

## How to Fix SQL Files

### Category 1: `is_primary` references (46 errors, 21 files)

`is_primary` now lives on `departments_resource` and `emails_resource`. Join the resource table to access it.

**Reads — finding primary department:**
```sql
-- OLD (is_primary on junction):
SELECT pd.departments_id
FROM profile_departments_junction pd
WHERE pd.profile_id = $1 AND pd.is_primary = true AND pd.active = true

-- NEW (is_primary on resource):
SELECT pd.departments_id
FROM profile_departments_junction pd
JOIN departments_resource dr ON dr.id = pd.departments_id
WHERE pd.profile_id = $1 AND dr.is_primary = true AND pd.active = true
```

**Reads — ordering by primary first:**
```sql
-- OLD:
ORDER BY pd.is_primary DESC, pd.created_at

-- NEW:
JOIN departments_resource dr ON dr.id = pd.departments_id
...
ORDER BY dr.is_primary DESC, pd.created_at
```

**Reads — checking if primary email:**
```sql
-- OLD:
pe.is_primary AS is_primary_email

-- NEW:
er.is_primary AS is_primary_email
...
JOIN emails_resource er ON er.id = pe.emails_id
```

**Writes — INSERT into junctions:**
```sql
-- OLD:
INSERT INTO profile_departments_junction (profile_id, departments_id, is_primary, ...)
VALUES ($1, $2, true, ...)

-- NEW (just remove is_primary from junction INSERT):
INSERT INTO profile_departments_junction (profile_id, departments_id, ...)
VALUES ($1, $2, ...)
-- If needed, separately UPDATE departments_resource SET is_primary = true WHERE id = $2
```

**Affected SQL files:**
```
server/app/sql/queries/auth/get_auth_complete.sql
server/app/sql/queries/auth/resolve_default_idp_profile_complete.sql
server/app/sql/queries/generate/text/get_text_run_context_for_existing_run_complete.sql
server/app/sql/queries/profile/create_or_update_profile_complete.sql
server/app/sql/queries/profile/create_profile_if_not_exists_complete.sql
server/app/sql/queries/profile/duplicate_profile_complete.sql
server/app/sql/queries/profile/get_profile_by_email_complete.sql
server/app/sql/queries/profile/get_profile_complete.sql
server/app/sql/queries/profile/get_profile_context_access_complete.sql
server/app/sql/queries/profile/get_profile_context_complete.sql
server/app/sql/queries/profile/get_profile_ids_complete.sql
server/app/sql/queries/profile/save_profile_complete.sql
server/app/sql/queries/profile/search_simulatable_profiles_complete.sql
server/app/sql/queries/profiles/get_profiles_list_complete.sql
server/app/sql/queries/profiles/get_profiles_search_complete.sql
server/app/sql/queries/profiles/upsert_profiles_complete.sql
server/app/sql/queries/rubrics/get_rubric_complete.sql
server/app/sql/queries/settings/get_active_settings_complete.sql
server/app/sql/queries/tools/get_tool_complete.sql
```

### Category 2: `field_id` → `fields_id` (25 errors, 7 files)

Pre-existing issue from migration 85. Replace `field_id` → `fields_id` in junction column references only (not CTE aliases or standalone column names).

```
server/app/sql/queries/fields/duplicate_field_complete.sql
server/app/sql/queries/fields/get_field_complete.sql
server/app/sql/queries/fields/get_fields_list_complete.sql
server/app/sql/queries/parameters/duplicate_parameter_complete.sql
server/app/sql/queries/parameters/get_parameter_complete.sql
server/app/sql/queries/parameters/get_parameters_list_complete.sql
server/app/sql/queries/resources/fields/search_fields_complete.sql
```

## Seed/Module Data Updates (10 files)

Remove `is_primary` from junction INSERT column lists and values. No new junction INSERTs needed.

```
database/modules/11-setups/organization/09-profiles/default-admin.sql
database/modules/11-setups/organization/09-profiles/default-guest.sql
database/modules/11-setups/organization/09-profiles/default-instructional.sql
database/modules/11-setups/organization/09-profiles/default-member.sql
database/modules/11-setups/organization/09-profiles/default-superadmin.sql
database/modules/11-setups/university/09-profiles/default-admin.sql
database/modules/11-setups/university/09-profiles/default-guest.sql
database/modules/11-setups/university/09-profiles/default-instructional.sql
database/modules/11-setups/university/09-profiles/default-member.sql
database/modules/11-setups/university/09-profiles/default-superadmin.sql
```

Example fix:
```sql
-- OLD:
INSERT INTO profile_departments_junction (profile_id, departments_id, is_primary, active, created_at, generated, mcp)
VALUES ('...', '...', true, true, '...', false, false)

-- NEW:
INSERT INTO profile_departments_junction (profile_id, departments_id, active, created_at, generated, mcp)
VALUES ('...', '...', true, '...', false, false)
```

Same pattern for `profile_emails_junction` — just remove `is_primary` column and value.

## Python Code Updates

1. **`server/app/routes/auth/permissions.py:117`** — References `is_primary=False`
2. **`server/app/sql/types.py`** — Will auto-regenerate after `make sql-compile` succeeds
3. **Resource types** — Add `is_primary: bool` to:
   - `server/app/routes/v5/tools/resources/departments/types.py` (`GetDepartmentResponse`)
   - `server/app/routes/v5/tools/resources/emails/types.py` (`GetEmailResponse`)

## Workflow

1. `git checkout` all files listed above to revert wrong changes
2. Fix SQL files (is_primary → resource JOIN, field_id → fields_id)
3. Fix seed/module files (remove is_primary from junction INSERTs)
4. Run `make sql-compile` — target 0 errors
5. Update Python types and references
6. Run `make test`
