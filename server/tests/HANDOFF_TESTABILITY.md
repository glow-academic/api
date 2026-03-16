# Testability Handoff

This note summarizes the low-level testability work completed in this branch and the best remaining targets for follow-up coverage.

## Refactored For Testability

- `app/utils/storage/file_writer.py`
- `app/infra/upload_paths.py`
- `app/infra/documents/read_document_content_for_similarity.py`
- `app/infra/documents/format_document_info.py`
- `app/infra/documents/format_document_template_context.py`
- `app/infra/websocket/handler_wrapper.py`
- `app/infra/websocket/generation_events_impl.py`
- `app/infra/websocket/generation_progress_impl.py`
- `app/infra/websocket/generation_ended_impl.py`
- `app/infra/websocket/generate_prepare_impl.py`
- `app/infra/websocket/run_complete_impl.py`
- websocket Redis/socket state helpers under `app/infra/websocket/`

## Real Bugs Fixed

- `app/utils/sql_nest.py`
- `app/utils/settings/theme.py`
- `app/utils/mcp/get_profile_id_from_claims.py`
- `app/utils/template_db.py`

## New Focused Coverage

Low-level direct coverage was added for:

- uploads and storage primitives
- document readers and document-formatting helpers
- MCP and header/profile resolution helpers
- SQL, text, theme, CSV, MIME, template, and error helpers
- websocket Redis/socket state helpers
- websocket payload builders and event helpers
- generation prepare/progress/ended/run-complete pure seams

Representative new helper-level test files:

- `tests/infra/test_generate_prepare_helpers.py`
- `tests/infra/test_run_complete_payloads.py`
- `tests/infra/test_generation_event_payloads.py`
- `tests/infra/test_generation_progress_payloads.py`
- `tests/infra/test_generation_ended_payloads.py`
- `tests/infra/test_handler_wrapper_error_payloads.py`
- `tests/infra/test_format_document_info.py`
- `tests/infra/test_format_document_template_context.py`
- `tests/infra/test_generate_artifact_helpers.py`

## Best Remaining Targets

These are the highest-value next modules if additional medium-sized coverage is needed:

1. `app/infra/artifacts/stream_litellm_events.py`
2. `app/infra/artifacts/discovery.py`
3. sliced extractions/tests from `app/infra/websocket/attempt_events_impl.py`

## Lower Priority

Avoid spending more time on:

- tiny leaf helpers
- passive model/default-only tests
- broad context modules unless doing heavier DB-backed integration coverage

## Testing Approach

- No full suite was run during this pass.
- Verification stayed targeted to the touched modules and their focused test files.
- The intent of these refactors is to help broader black-box testing proceed without mocks.
