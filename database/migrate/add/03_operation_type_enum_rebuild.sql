-- ══════════════════════════════════════════════════════════════
-- Migration 03 (add): Rebuild operation_type enum
--
-- Changes:
--   REMOVE: events, use_previous, audio
--   ADD:    previous, csv,
--           image_upload, image_download,
--           video_upload, video_download,
--           text_upload, text_download,
--           file_upload, file_download, file_preview,
--           audio_start, audio_frame, audio_stop, audio_mute,
--           audio_upload, audio_download,
--           call_download
--
-- Strategy: create new type → cast column to text → rename values
--           → cast column to new type → drop old → rename new
-- ══════════════════════════════════════════════════════════════

-- 1. Create the new enum with all correct values
CREATE TYPE public.operation_type_new AS ENUM (
    -- Standard CRUD
    'get',
    'search',
    'create',
    'update',
    'delete',
    'duplicate',
    'draft',
    'drafts',
    'export',
    'refresh',
    'docs',
    'csv',
    -- Attempt/test state machine
    'start',
    'next',
    'end',
    'end_all',
    'message',
    'grade',
    'stop',
    'response',
    'previous',
    'archive',
    -- Image
    'image_upload',
    'image_download',
    -- Video
    'video_upload',
    'video_download',
    -- Text
    'text_upload',
    'text_download',
    -- File
    'file_upload',
    'file_download',
    'file_preview',
    -- Audio
    'audio_start',
    'audio_frame',
    'audio_stop',
    'audio_mute',
    'audio_upload',
    'audio_download',
    -- Call
    'call_download',
    -- Artifact-specific
    'run',
    'generate',
    'problem',
    'resolve',
    'emulate',
    'unemulate',
    'context',
    'decrypt'
);

-- 2. Cast column to TEXT so we can rename values
ALTER TABLE permissions_resource
    ALTER COLUMN operation TYPE TEXT;

-- 3. Rename old values
UPDATE permissions_resource SET operation = 'previous'     WHERE operation = 'use_previous';
UPDATE permissions_resource SET operation = 'audio_start'  WHERE operation = 'audio';

-- 4. Delete rows with removed operations
DELETE FROM permissions_resource WHERE operation = 'events';

-- 5. Cast column to new enum type
ALTER TABLE permissions_resource
    ALTER COLUMN operation TYPE public.operation_type_new
    USING operation::public.operation_type_new;

-- 6. Drop old type, rename new
DROP TYPE public.operation_type;
ALTER TYPE public.operation_type_new RENAME TO operation_type;

-- 7. Track migration
INSERT INTO migration_tracking (migration_number, migration_file, migration_type) VALUES
  (3, '03_operation_type_enum_rebuild.sql', 'add')
ON CONFLICT (migration_number, migration_type) DO NOTHING;
