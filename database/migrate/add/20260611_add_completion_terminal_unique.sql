-- Terminal-unique constraints on the completion-entry siblings — make a
-- duplicate completion idempotent instead of appending a SECOND active row
-- (C1-B). This mirrors attempt_completion_entry's UNIQUE(attempt_id) (#339 B1)
-- and attempt_chat_completion_entry's UNIQUE(chat_id): at most ONE completion
-- row per parent. The create.py for each entry now does
-- INSERT ... ON CONFLICT (<parent_fk>) DO UPDATE SET active=true WHERE the
-- existing row is dormant and the incoming row is hard — so a hard complete
-- supersedes a dormant soft proposal, an accepted completion is never
-- clobbered, and a duplicate hard complete is a no-op. These constraints are
-- the hard backstop that the ON CONFLICT clause infers against.
--
-- PRE-DEDUP (self-healing): a bare ADD CONSTRAINT UNIQUE raises a unique
-- violation on exactly the instances that hit the pre-fix duplicate-completion
-- bug (the ones with >1 row per parent). Without a dedup pass the runner rolls
-- the file's whole transaction back (incl. its migrations.applied insert) and
-- it fails identically on every subsequent deploy — the backstop never lands
-- where it is needed. So collapse duplicate rows FIRST, then add the
-- constraint.
--
-- Which row to keep: the one the *_completion_mv would surface. Those MVs are
-- a passthrough WHERE active = true; consumers that fold them to a single
-- completion (e.g. test_invocation_mv.latest_completion) use
-- DISTINCT ON (parent) ... ORDER BY created_at DESC. So per parent keep the
-- latest active row (active DESC, created_at DESC, id DESC as a deterministic
-- tie-break) and delete the rest. Idempotent: on a clean instance no parent has
-- >1 row, so the DELETE removes nothing.
--
-- ADD CONSTRAINT is guarded by a NOT EXISTS check on pg_constraint so the file
-- is safely re-runnable (the migrate runner already dedups on filename, but the
-- guard keeps each statement independently idempotent).

-- test_completion (parent: test_id)
WITH ranked AS (
    SELECT id, row_number() OVER (
        PARTITION BY test_id ORDER BY active DESC, created_at DESC, id DESC
    ) AS rn
    FROM public.test_completion_entry
)
DELETE FROM public.test_completion_entry t USING ranked r
WHERE t.id = r.id AND r.rn > 1;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'test_completion_entry_test_unique') THEN
        ALTER TABLE public.test_completion_entry
            ADD CONSTRAINT test_completion_entry_test_unique UNIQUE (test_id);
    END IF;
END $$;

-- file_completion (parent: file_id)
WITH ranked AS (
    SELECT id, row_number() OVER (
        PARTITION BY file_id ORDER BY active DESC, created_at DESC, id DESC
    ) AS rn
    FROM public.file_completion_entry
)
DELETE FROM public.file_completion_entry t USING ranked r
WHERE t.id = r.id AND r.rn > 1;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'file_completion_entry_file_unique') THEN
        ALTER TABLE public.file_completion_entry
            ADD CONSTRAINT file_completion_entry_file_unique UNIQUE (file_id);
    END IF;
END $$;

-- image_completion (parent: image_id)
WITH ranked AS (
    SELECT id, row_number() OVER (
        PARTITION BY image_id ORDER BY active DESC, created_at DESC, id DESC
    ) AS rn
    FROM public.image_completion_entry
)
DELETE FROM public.image_completion_entry t USING ranked r
WHERE t.id = r.id AND r.rn > 1;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'image_completion_entry_image_unique') THEN
        ALTER TABLE public.image_completion_entry
            ADD CONSTRAINT image_completion_entry_image_unique UNIQUE (image_id);
    END IF;
END $$;

-- video_completion (parent: video_id)
WITH ranked AS (
    SELECT id, row_number() OVER (
        PARTITION BY video_id ORDER BY active DESC, created_at DESC, id DESC
    ) AS rn
    FROM public.video_completion_entry
)
DELETE FROM public.video_completion_entry t USING ranked r
WHERE t.id = r.id AND r.rn > 1;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'video_completion_entry_video_unique') THEN
        ALTER TABLE public.video_completion_entry
            ADD CONSTRAINT video_completion_entry_video_unique UNIQUE (video_id);
    END IF;
END $$;

-- audio_completion (parent: audio_id)
WITH ranked AS (
    SELECT id, row_number() OVER (
        PARTITION BY audio_id ORDER BY active DESC, created_at DESC, id DESC
    ) AS rn
    FROM public.audio_completion_entry
)
DELETE FROM public.audio_completion_entry t USING ranked r
WHERE t.id = r.id AND r.rn > 1;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audio_completion_entry_audio_unique') THEN
        ALTER TABLE public.audio_completion_entry
            ADD CONSTRAINT audio_completion_entry_audio_unique UNIQUE (audio_id);
    END IF;
END $$;

-- text_completion (parent: text_id)
WITH ranked AS (
    SELECT id, row_number() OVER (
        PARTITION BY text_id ORDER BY active DESC, created_at DESC, id DESC
    ) AS rn
    FROM public.text_completion_entry
)
DELETE FROM public.text_completion_entry t USING ranked r
WHERE t.id = r.id AND r.rn > 1;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'text_completion_entry_text_unique') THEN
        ALTER TABLE public.text_completion_entry
            ADD CONSTRAINT text_completion_entry_text_unique UNIQUE (text_id);
    END IF;
END $$;

-- upload_completion (parent: upload_id)
WITH ranked AS (
    SELECT id, row_number() OVER (
        PARTITION BY upload_id ORDER BY active DESC, created_at DESC, id DESC
    ) AS rn
    FROM public.upload_completion_entry
)
DELETE FROM public.upload_completion_entry t USING ranked r
WHERE t.id = r.id AND r.rn > 1;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'upload_completion_entry_upload_unique') THEN
        ALTER TABLE public.upload_completion_entry
            ADD CONSTRAINT upload_completion_entry_upload_unique UNIQUE (upload_id);
    END IF;
END $$;

-- test_invocation_completion (parent: invocation_id)
WITH ranked AS (
    SELECT id, row_number() OVER (
        PARTITION BY invocation_id ORDER BY active DESC, created_at DESC, id DESC
    ) AS rn
    FROM public.test_invocation_completion_entry
)
DELETE FROM public.test_invocation_completion_entry t USING ranked r
WHERE t.id = r.id AND r.rn > 1;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'test_invocation_completion_entry_invocation_unique') THEN
        ALTER TABLE public.test_invocation_completion_entry
            ADD CONSTRAINT test_invocation_completion_entry_invocation_unique UNIQUE (invocation_id);
    END IF;
END $$;
