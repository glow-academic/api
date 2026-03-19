"""Backup service — list available backups from the history volume.

Backups are created by:
- Pre-deploy: pg_dump in deploy.yml (inside database container, always correct)
- Scheduled: backup-cron sidecar (weekly, configurable)

The server only reads the history volume — it does not create backups.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

HISTORY_DIR = Path(os.getenv("HISTORY_DIR", "/app/history"))


def list_backups() -> list[dict]:
    """List all backup files in the history directory."""
    hdir = HISTORY_DIR
    if not hdir.exists():
        return []
    backups = []
    for f in sorted(hdir.glob("*.sql.gz")):
        stat = f.stat()
        backups.append({
            "name": f.name,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return backups
