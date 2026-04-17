-- ══════════════════════════════════════════════════════════════
-- Migration 30: Consolidate VIEW artifacts into parent groups
--
-- Removes 14 VIEW artifacts, folds them into 3 parents:
--   attempt ← home, practice, chat, dashboard, leaderboard, reports, record
--   test    ← invocation, benchmark
--   system  ← activity, session, pricing, group, health
--
-- Operations become compound: (home, get) → (attempt, home_get)
-- IDs are preserved — role permission_ids arrays remain valid.
--
-- One collision: (chat, get) → (attempt, chat_get) already exists.
-- Handled by merging references and deleting the duplicate.
-- ══════════════════════════════════════════════════════════════

-- ============================================================================
-- Step 1: Add 'system' to artifact_type enum
-- ============================================================================

ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'system';

-- ============================================================================
-- Step 2: Add compound operation_type values
-- ============================================================================

-- attempt ← home (9)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'home_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'home_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'home_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'home_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'home_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'home_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'home_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'home_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'home_search';

-- attempt ← practice (9)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'practice_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'practice_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'practice_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'practice_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'practice_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'practice_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'practice_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'practice_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'practice_search';

-- attempt ← chat (6, chat_get already exists)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'chat_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'chat_draft';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'chat_drafts';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'chat_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'chat_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'chat_search';

-- attempt ← dashboard (9)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'dashboard_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'dashboard_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'dashboard_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'dashboard_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'dashboard_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'dashboard_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'dashboard_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'dashboard_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'dashboard_search';

-- attempt ← leaderboard (9)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'leaderboard_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'leaderboard_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'leaderboard_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'leaderboard_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'leaderboard_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'leaderboard_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'leaderboard_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'leaderboard_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'leaderboard_search';

-- attempt ← reports (9)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'reports_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'reports_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'reports_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'reports_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'reports_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'reports_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'reports_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'reports_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'reports_search';

-- attempt ← record (9)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'record_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'record_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'record_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'record_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'record_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'record_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'record_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'record_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'record_search';

-- test ← invocation (12)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_decrypt';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_draft';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_drafts';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'invocation_search';

-- test ← benchmark (9)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'benchmark_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'benchmark_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'benchmark_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'benchmark_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'benchmark_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'benchmark_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'benchmark_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'benchmark_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'benchmark_search';

-- system ← activity (10)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'activity_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'activity_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'activity_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'activity_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'activity_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'activity_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'activity_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'activity_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'activity_resolve';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'activity_search';

-- system ← session (9)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'session_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'session_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'session_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'session_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'session_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'session_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'session_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'session_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'session_search';

-- system ← pricing (9)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'pricing_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'pricing_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'pricing_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'pricing_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'pricing_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'pricing_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'pricing_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'pricing_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'pricing_search';

-- system ← group (16)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_audio_download';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_call_download';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_file_download';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_file_preview';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_image_download';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_name';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_search';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_text_download';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'group_video_download';

-- system ← health (9)
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'health_context';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'health_export';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'health_generate';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'health_generations';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'health_get';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'health_group';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'health_problem';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'health_refresh';
ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'health_search';

-- ============================================================================
-- Step 3: Handle collision — (chat, get) → (attempt, chat_get) already exists
-- ============================================================================

-- Replace old (chat, get) ID with existing (attempt, chat_get) ID in roles
UPDATE roles_resource
SET permission_ids = array_replace(
    permission_ids,
    (SELECT id FROM permissions_resource WHERE artifact = 'chat' AND operation = 'get'),
    (SELECT id FROM permissions_resource WHERE artifact = 'attempt' AND operation = 'chat_get')
)
WHERE (SELECT id FROM permissions_resource WHERE artifact = 'chat' AND operation = 'get') = ANY(permission_ids);

-- Same for tools
UPDATE tools_resource
SET permission_ids = array_replace(
    permission_ids,
    (SELECT id FROM permissions_resource WHERE artifact = 'chat' AND operation = 'get'),
    (SELECT id FROM permissions_resource WHERE artifact = 'attempt' AND operation = 'chat_get')
)
WHERE (SELECT id FROM permissions_resource WHERE artifact = 'chat' AND operation = 'get') = ANY(permission_ids);

-- Same for tool_permissions_junction
UPDATE tool_permissions_junction
SET permissions_id = (SELECT id FROM permissions_resource WHERE artifact = 'attempt' AND operation = 'chat_get')
WHERE permissions_id = (SELECT id FROM permissions_resource WHERE artifact = 'chat' AND operation = 'get');

-- Same for tool_drafts_permissions_connection
UPDATE tool_drafts_permissions_connection
SET permissions_id = (SELECT id FROM permissions_resource WHERE artifact = 'attempt' AND operation = 'chat_get')
WHERE permissions_id = (SELECT id FROM permissions_resource WHERE artifact = 'chat' AND operation = 'get');

-- Delete the duplicate row
DELETE FROM permissions_resource WHERE artifact = 'chat' AND operation = 'get';

-- ============================================================================
-- Step 4: Bulk-update remaining 134 permissions via temp mapping table
-- ============================================================================

CREATE TEMP TABLE _perm_map (old_art text, old_op text, new_art text, new_op text);

INSERT INTO _perm_map VALUES
-- attempt ← home
('home', 'context', 'attempt', 'home_context'),
('home', 'export', 'attempt', 'home_export'),
('home', 'generate', 'attempt', 'home_generate'),
('home', 'generations', 'attempt', 'home_generations'),
('home', 'get', 'attempt', 'home_get'),
('home', 'group', 'attempt', 'home_group'),
('home', 'problem', 'attempt', 'home_problem'),
('home', 'refresh', 'attempt', 'home_refresh'),
('home', 'search', 'attempt', 'home_search'),
-- attempt ← practice
('practice', 'context', 'attempt', 'practice_context'),
('practice', 'export', 'attempt', 'practice_export'),
('practice', 'generate', 'attempt', 'practice_generate'),
('practice', 'generations', 'attempt', 'practice_generations'),
('practice', 'get', 'attempt', 'practice_get'),
('practice', 'group', 'attempt', 'practice_group'),
('practice', 'problem', 'attempt', 'practice_problem'),
('practice', 'refresh', 'attempt', 'practice_refresh'),
('practice', 'search', 'attempt', 'practice_search'),
-- attempt ← chat (excluding get — handled in step 3)
('chat', 'context', 'attempt', 'chat_context'),
('chat', 'draft', 'attempt', 'chat_draft'),
('chat', 'drafts', 'attempt', 'chat_drafts'),
('chat', 'export', 'attempt', 'chat_export'),
('chat', 'refresh', 'attempt', 'chat_refresh'),
('chat', 'search', 'attempt', 'chat_search'),
-- attempt ← dashboard
('dashboard', 'context', 'attempt', 'dashboard_context'),
('dashboard', 'export', 'attempt', 'dashboard_export'),
('dashboard', 'generate', 'attempt', 'dashboard_generate'),
('dashboard', 'generations', 'attempt', 'dashboard_generations'),
('dashboard', 'get', 'attempt', 'dashboard_get'),
('dashboard', 'group', 'attempt', 'dashboard_group'),
('dashboard', 'problem', 'attempt', 'dashboard_problem'),
('dashboard', 'refresh', 'attempt', 'dashboard_refresh'),
('dashboard', 'search', 'attempt', 'dashboard_search'),
-- attempt ← leaderboard
('leaderboard', 'context', 'attempt', 'leaderboard_context'),
('leaderboard', 'export', 'attempt', 'leaderboard_export'),
('leaderboard', 'generate', 'attempt', 'leaderboard_generate'),
('leaderboard', 'generations', 'attempt', 'leaderboard_generations'),
('leaderboard', 'get', 'attempt', 'leaderboard_get'),
('leaderboard', 'group', 'attempt', 'leaderboard_group'),
('leaderboard', 'problem', 'attempt', 'leaderboard_problem'),
('leaderboard', 'refresh', 'attempt', 'leaderboard_refresh'),
('leaderboard', 'search', 'attempt', 'leaderboard_search'),
-- attempt ← reports
('reports', 'context', 'attempt', 'reports_context'),
('reports', 'export', 'attempt', 'reports_export'),
('reports', 'generate', 'attempt', 'reports_generate'),
('reports', 'generations', 'attempt', 'reports_generations'),
('reports', 'get', 'attempt', 'reports_get'),
('reports', 'group', 'attempt', 'reports_group'),
('reports', 'problem', 'attempt', 'reports_problem'),
('reports', 'refresh', 'attempt', 'reports_refresh'),
('reports', 'search', 'attempt', 'reports_search'),
-- attempt ← record
('record', 'context', 'attempt', 'record_context'),
('record', 'export', 'attempt', 'record_export'),
('record', 'generate', 'attempt', 'record_generate'),
('record', 'generations', 'attempt', 'record_generations'),
('record', 'get', 'attempt', 'record_get'),
('record', 'group', 'attempt', 'record_group'),
('record', 'problem', 'attempt', 'record_problem'),
('record', 'refresh', 'attempt', 'record_refresh'),
('record', 'search', 'attempt', 'record_search'),
-- test ← invocation
('invocation', 'context', 'test', 'invocation_context'),
('invocation', 'decrypt', 'test', 'invocation_decrypt'),
('invocation', 'draft', 'test', 'invocation_draft'),
('invocation', 'drafts', 'test', 'invocation_drafts'),
('invocation', 'export', 'test', 'invocation_export'),
('invocation', 'generate', 'test', 'invocation_generate'),
('invocation', 'generations', 'test', 'invocation_generations'),
('invocation', 'get', 'test', 'invocation_get'),
('invocation', 'group', 'test', 'invocation_group'),
('invocation', 'problem', 'test', 'invocation_problem'),
('invocation', 'refresh', 'test', 'invocation_refresh'),
('invocation', 'search', 'test', 'invocation_search'),
-- test ← benchmark
('benchmark', 'context', 'test', 'benchmark_context'),
('benchmark', 'export', 'test', 'benchmark_export'),
('benchmark', 'generate', 'test', 'benchmark_generate'),
('benchmark', 'generations', 'test', 'benchmark_generations'),
('benchmark', 'get', 'test', 'benchmark_get'),
('benchmark', 'group', 'test', 'benchmark_group'),
('benchmark', 'problem', 'test', 'benchmark_problem'),
('benchmark', 'refresh', 'test', 'benchmark_refresh'),
('benchmark', 'search', 'test', 'benchmark_search'),
-- system ← activity
('activity', 'context', 'system', 'activity_context'),
('activity', 'export', 'system', 'activity_export'),
('activity', 'generate', 'system', 'activity_generate'),
('activity', 'generations', 'system', 'activity_generations'),
('activity', 'get', 'system', 'activity_get'),
('activity', 'group', 'system', 'activity_group'),
('activity', 'problem', 'system', 'activity_problem'),
('activity', 'refresh', 'system', 'activity_refresh'),
('activity', 'resolve', 'system', 'activity_resolve'),
('activity', 'search', 'system', 'activity_search'),
-- system ← session
('session', 'context', 'system', 'session_context'),
('session', 'export', 'system', 'session_export'),
('session', 'generate', 'system', 'session_generate'),
('session', 'generations', 'system', 'session_generations'),
('session', 'get', 'system', 'session_get'),
('session', 'group', 'system', 'session_group'),
('session', 'problem', 'system', 'session_problem'),
('session', 'refresh', 'system', 'session_refresh'),
('session', 'search', 'system', 'session_search'),
-- system ← pricing
('pricing', 'context', 'system', 'pricing_context'),
('pricing', 'export', 'system', 'pricing_export'),
('pricing', 'generate', 'system', 'pricing_generate'),
('pricing', 'generations', 'system', 'pricing_generations'),
('pricing', 'get', 'system', 'pricing_get'),
('pricing', 'group', 'system', 'pricing_group'),
('pricing', 'problem', 'system', 'pricing_problem'),
('pricing', 'refresh', 'system', 'pricing_refresh'),
('pricing', 'search', 'system', 'pricing_search'),
-- system ← group
('group', 'audio_download', 'system', 'group_audio_download'),
('group', 'call_download', 'system', 'group_call_download'),
('group', 'context', 'system', 'group_context'),
('group', 'export', 'system', 'group_export'),
('group', 'file_download', 'system', 'group_file_download'),
('group', 'file_preview', 'system', 'group_file_preview'),
('group', 'generate', 'system', 'group_generate'),
('group', 'generations', 'system', 'group_generations'),
('group', 'get', 'system', 'group_get'),
('group', 'group', 'system', 'group_group'),
('group', 'image_download', 'system', 'group_image_download'),
('group', 'name', 'system', 'group_name'),
('group', 'problem', 'system', 'group_problem'),
('group', 'refresh', 'system', 'group_refresh'),
('group', 'search', 'system', 'group_search'),
('group', 'text_download', 'system', 'group_text_download'),
('group', 'video_download', 'system', 'group_video_download'),
-- system ← health
('health', 'context', 'system', 'health_context'),
('health', 'export', 'system', 'health_export'),
('health', 'generate', 'system', 'health_generate'),
('health', 'generations', 'system', 'health_generations'),
('health', 'get', 'system', 'health_get'),
('health', 'group', 'system', 'health_group'),
('health', 'problem', 'system', 'health_problem'),
('health', 'refresh', 'system', 'health_refresh'),
('health', 'search', 'system', 'health_search');

-- Bulk update: remap artifact + operation, update name
UPDATE permissions_resource p
SET
    artifact = m.new_art::artifact_type,
    operation = m.new_op::operation_type,
    name = initcap(replace(m.new_op, '_', ' ')) || ' ' || initcap(m.new_art)
FROM _perm_map m
WHERE p.artifact::text = m.old_art
  AND p.operation::text = m.old_op;

DROP TABLE _perm_map;

-- ============================================================================
-- Step 5: Track migration
-- ============================================================================

INSERT INTO migration_tracking (migration_number, migration_file, migration_type) VALUES
  (30, '30_consolidate_view_artifacts.sql', 'add')
ON CONFLICT (migration_number, migration_type) DO NOTHING;
