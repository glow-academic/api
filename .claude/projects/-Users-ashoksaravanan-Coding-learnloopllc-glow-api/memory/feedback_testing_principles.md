---
name: Testing Principles
description: Core testing philosophy and conventions for glow-api — DI via params, no monkeypatching, black-box tools, no fake seeding, minimal fixtures, canonical naming, socket dot-notation, 1:1 file mapping, no unit/integration split, route testing via ASGI client, socket emit recording, infra splitting
type: feedback
---

## Core Testing Principles

### 1. Dependency Injection via Function Parameters
- Every function accepts its deps (`conn`, `pool`, `redis`, `emit`) as parameters.
- Tools take `conn: asyncpg.Connection` — the caller provides it.
- Infra functions take `pool: asyncpg.Pool` and `redis: Redis`.
- Socket business logic accepts `emit: EmitFn` — production passes `make_emit()`, tests pass `recording_emit()`.
- If a function is hard to test without patching, fix the design, not the test.

### 2. No Monkeypatching
- Zero `monkeypatch` / `mock.patch` usage. Dependencies are swapped via function signatures.
- The only "override" in tests is directly assigning globals for route client setup (`globals_mod._db_pool = test_pool`), which is explicit and scoped.

### 3. Black-Box Tool Contracts
- `app/tools/{artifacts,resources,entries}/{name}/` define pure async functions with clear input/output types.
- Tests call tools directly with a real `conn` and assert on the returned dataclass.
- Never mock a tool's internals or peek at its SQL — trust the contract boundary.
- Example: `create_agent(conn, name_id=..., department_ids=...) -> CreateAgentResponse`.

### 4. No Fake Seeding
- No seed files, no synthetic fixtures dumped into the DB.
- Tests build state through the same tool functions production uses: `create_name()`, `create_profile()`, `create_agent()`.
- `unique_tag()` (uuid4 hex[:8]) ensures test data isolation without collisions.
- `nonexistent_id()` (uuid4) for "returns empty" assertions.

### 5. Fixtures Only When Genuinely Shared
- Root `conftest.py` fixtures: `pool`, `conn`, `redis_client`, entity chain (`profile_id` -> `department_id` -> `session_id` -> `group_id` -> `run_id` -> `call_id`).
- Infra `conftest.py`: route clients (`v5_{artifact}_route_client`), factories (`setting_graph_factory`, `system_graph_factory`).
- Inline setup preferred for single-test scenarios — helper functions like `_create_agent_route_resources()` live in the test file, not as fixtures.
- Bundles as frozen dataclasses (e.g., `SimulationBundle`, `AgentRouteResources`, `RouteActor`) when multiple IDs travel together.

### 6. Canonical / Proper Naming
- Test class: `Test{Feature}` — e.g., `TestAgentRoute`, `TestFlushEvents`, `TestSocketEventConstruction`.
- Test method: `test_{operation}_{what_it_verifies}` — e.g., `test_create_agent_route_uses_real_http_stack`, `test_delete_agent_route_hides_deleted_agent_from_search`.
- Private helpers: `_create_{resource}_via_{layer}()` — underscore prefix.
- Names read as specifications of behavior, not implementation.

### 7. Socket Event Naming: Dot Notation = Folder Structure
- `@sio.on("agent.create")` lives in `app/ws/v5/input/agent/create.py`.
- `@sio.on("attempt.audio_start")` lives in `app/ws/v5/input/attempt/audio_start.py`.
- Convert dots to path separators to find the handler.

### 8. Socket Handlers Return Events for Testability
- Business logic accepts `emit: EmitFn` and calls `await emit([...events])`.
- `SocketEvent` is a frozen dataclass with `bus`, `event`, `data`, `room`, `sid`.
- Production: `emit = make_emit(client_sio=sio, internal_sio=internal_sio)` — wraps `flush_events`.
- Tests: `emit, events = recording_emit()` — spy that captures all events in order.
- Assert on the `events` list to verify both content and emission order.

### 9. No Unit vs Integration Split
- There is one `tests/` directory. No separate `unit/` and `integration/` folders.
- All tests run against real testcontainers (Postgres + Redis). Pure functions are tested as plain sync tests within the same tree.
- No distinction in runner config — all tests are just tests.

### 10. One Test File Per Source File (1:1 Mapping)
- `app/routes/v5/agent/` -> `tests/infra/routes/v5/agent/test_route.py`
- `app/infra/websocket/socket_event.py` -> `tests/infra/socket/v5/test_socket_event.py`
- `app/infra/websocket/generation_events_impl.py` -> `tests/infra/socket/v5/generation/test_generation_event_payloads.py`
- Test file prefix is `test_` on the filename.

### 11. Route Testing: Real ASGI Stack
- Routes tested via `httpx.AsyncClient` with `ASGITransport` — real HTTP serialization, no mocked request objects.
- `V5RouteClient` dataclass wraps the async client + auth state.
- Each artifact gets its own route client fixture (`v5_agent_route_client`) that mounts only that artifact's router.
- Auth override via FastAPI dependency injection (`require_auth` overridden with test identity).
- Tests assert on: status codes, cache headers (`X-Cache-Tags`, `X-Invalidate-Tags`, `X-Cache-Hit`), response payload structure.

### 12. Infra Folder: One Module Per Concern Per Artifact
- `app/infra/{artifact}/` contains one file per operation: `create.py`, `get.py`, `search.py`, `update.py`, `delete.py`, `duplicate.py`, `draft.py`, `drafts.py`, `docs.py`, `export.py`, `refresh.py`.
- Plus: `types.py` (Pydantic models), `permissions.py`, `permissions_context.py`, `context.py`, `sections.py`.
- Each file is a composable function, not a class — `create_agent_impl(pool, redis, ...)`.

### 13. Three-Layer Architecture: Route -> Infra -> Tool
- **Route** (thin adapter): extract auth state, parse request, call infra impl, return response.
- **Infra** (orchestration): resolve identity, check permissions, validate per-item, compose tools, invalidate cache.
- **Tool** (black box): pure data access — INSERT/SELECT with junction writes, returns typed response.
- Each layer is independently testable. Route tests go through ASGI. Tool tests call functions directly with `conn`.

### 14. Test Data Isolation
- Each test gets a fresh `asyncpg.Pool` (pool fixture) or a transaction-wrapped `conn` that rolls back.
- Redis is flushed before and after each test.
- `unique_tag()` ensures names/descriptions don't collide across parallel tests.
- Testcontainer template caching: schema hash determines template reuse for fast cold/warm starts.
