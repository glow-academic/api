# Infrastructure v5 Standards

This document defines the standards and best practices for Infrastructure v5 utilities.

## Overview

Infrastructure utilities are categorized into three types:

1. **Database Operations**: Utilities that interact with PostgreSQL via black box entry functions or inline SQL
2. **Redis Operations**: Utilities that interact with Redis (follow consistent patterns)
3. **Pure Python Utilities**: Utilities that don't interact with database/Redis (standard Python patterns)

## Key Principles

### 1. Database Operations: Entry Functions and Inline SQL

**Mutations** use black box entry functions from `server/app/routes/v5/tools/entries/`:

```python
from app.routes.v5.tools.entries.calls.create import create_call
from app.routes.v5.tools.entries.groups.create import create_group
from app.routes.v5.tools.entries.runs.create import create_run

# Standard mutation chain: group → run → call → domain entry
group_result = await create_group(conn, session_id=session_id)
run_result = await create_run(conn, group_id=group_result.id, session_id=session_id)
call_result = await create_call(conn, run_id=run_result.id, session_id=session_id)
```

**Reads** use inline SQL or `*_internal()` resource/view functions.

**Discovery queries** (e.g., introspecting pg_proc, information_schema) use inline SQL directly.

### 2. Hand-Crafted Pydantic Types

- **Shared types**: `server/app/routes/shared_types.py` for cross-route types
- **Per-route types**: `types.py` files alongside route handlers
- Types are manually maintained Pydantic BaseModel subclasses

### 3. No JSONB - Use Composite Types

**Key Principles:**

- **No JSONB in inputs**: Function parameters must use native PostgreSQL types (`uuid`, `text`, `uuid[]`, etc.) or composite types, never JSONB
- **Composite types for complex inputs**: If you need complex nested structures, use composite types as function parameters
- **No JSONB in outputs**: Collections are arrays, not JSONB objects
- **Lists everywhere**: All collections return as arrays of composite types, not nested JSONB structures

### 4. Type Preservation

When defining composite types, use native PostgreSQL types (`uuid`, `timestamptz`) instead of stringifying them to `text` unless there's a specific reason.

### 5. Redis Operations Pattern

Infrastructure utilities that interact with Redis should follow these patterns:

1. **Consistent error handling**: Always fallback to in-memory storage when Redis unavailable
2. **Key naming**: Use consistent prefixes (`socket_owner:`, `active_connection:`, `active_run:`)
3. **No logging**: Redis operations should not log errors (let callers handle logging)
4. **Type hints**: All functions should have complete type hints

**Example Pattern:**

```python
"""Get the active run ID for a chat from Redis."""

from app.infra.globals import get_redis_client

async def get_active_run(chat_id: str) -> str | None:
    """Get the active run ID for a chat from Redis."""
    redis_client = get_redis_client()
    if not redis_client:
        return None

    try:
        run_id = await redis_client.get(f"active_run:{chat_id}")
        return run_id.decode("utf-8") if run_id else None
    except Exception:
        return None
```

### 6. Pure Python Utilities Pattern

Infrastructure utilities that don't interact with database/Redis should follow standard Python patterns:

1. **Type hints**: All functions should have complete type hints
2. **Documentation**: All public functions should have docstrings
3. **No side effects**: Pure utilities should be deterministic and have no side effects

**Example Pattern:**

```python
"""Database connection helper for WebSocket handlers."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg

from app.infra.globals import get_pool

@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Get database connection for WebSocket handlers."""
    pool = get_pool()
    if not pool:
        raise RuntimeError("Database connection pool not initialized")

    async with pool.acquire() as connection:
        yield connection
```

## Testing Checklist

### Database Operations

- [ ] Uses entry functions for mutations (group→run→call chain)
- [ ] Hand-crafted Pydantic types match expected data shapes
- [ ] No JSONB parsing in Python file — no `json.loads()` calls
- [ ] Integration tests pass

### Redis Operations

- [ ] Fallback to in-memory storage when Redis unavailable
- [ ] Consistent key naming patterns
- [ ] No logging in Redis operations
- [ ] Type hints complete

### Pure Python Utilities

- [ ] Type hints complete
- [ ] Documentation complete
- [ ] No side effects (if applicable)

## Benefits

1. **Simplicity**: No SQL compilation pipeline — types are hand-crafted and immediately available
2. **Reusability**: Black box entry functions provide consistent mutation patterns
3. **Strong Typing**: Pydantic enforces types at Python level, PostgreSQL at database level
4. **Maintainability**: Entry functions encapsulate database operations, reducing boilerplate
5. **Developer Experience**: No build step for types — edit and go
