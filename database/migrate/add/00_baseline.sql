-- Baseline migration: migration tracking table only.
-- Full schema is provided by fresh.sql.gz backup or prior migrations.

-- ══════════════════════════════════════════════════════════════
-- Migration Tracking
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS migration_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    migration_number INTEGER NOT NULL,
    migration_file VARCHAR(255) NOT NULL,
    migration_type VARCHAR(10) NOT NULL CHECK (migration_type IN ('add', 'remove')),
    applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    applied_by VARCHAR(255),
    CONSTRAINT migration_tracking_unique UNIQUE (migration_number, migration_type)
);

CREATE INDEX IF NOT EXISTS idx_migration_tracking_number ON migration_tracking (migration_number DESC);
CREATE INDEX IF NOT EXISTS idx_migration_tracking_type ON migration_tracking (migration_type);

-- ══════════════════════════════════════════════════════════════
-- Record baseline as applied
-- ══════════════════════════════════════════════════════════════

INSERT INTO migration_tracking (migration_number, migration_file, migration_type) VALUES
  (0, '00_baseline.sql', 'add')
ON CONFLICT (migration_number, migration_type) DO NOTHING;
