-- v2.15.21_01_drop_legacy_calls_connections.sql
--
-- Drops the 62 legacy ``<resource>_calls_connection`` tables that
-- linked individual resources directly to ``calls_entry`` rows. They
-- were the old paradigm for "which call minted this resource"; the
-- canonical ``soft_calls_entry`` ledger (v2.15.20) replaces this with
-- a unified `(call_id, artifact, operation, status, artifact_id)`
-- shape that covers ack lifecycle AND audit forensics in one place.
--
-- ``tools_calls_connection`` is intentionally KEPT — it links each
-- ``calls_entry`` row to the ``tools_resource`` it was a call to and is
-- part of the ``calls_mv`` definition. That mapping is structural,
-- not lifecycle.
--
-- Whole migration runs inside one transaction. ``IF EXISTS`` so the
-- migration is safe to re-run on environments where some tables were
-- already pruned.

BEGIN;

DROP TABLE IF EXISTS public.agents_calls_connection;
DROP TABLE IF EXISTS public.auth_item_keys_calls_connection;
DROP TABLE IF EXISTS public.auths_calls_connection;
DROP TABLE IF EXISTS public.cohorts_calls_connection;
DROP TABLE IF EXISTS public.colors_calls_connection;
DROP TABLE IF EXISTS public.conditional_parameters_calls_connection;
DROP TABLE IF EXISTS public.departments_calls_connection;
DROP TABLE IF EXISTS public.descriptions_calls_connection;
DROP TABLE IF EXISTS public.documents_calls_connection;
DROP TABLE IF EXISTS public.emails_calls_connection;
DROP TABLE IF EXISTS public.endpoints_calls_connection;
DROP TABLE IF EXISTS public.evals_calls_connection;
DROP TABLE IF EXISTS public.examples_calls_connection;
DROP TABLE IF EXISTS public.fields_calls_connection;
DROP TABLE IF EXISTS public.files_calls_connection;
DROP TABLE IF EXISTS public.flags_calls_connection;
DROP TABLE IF EXISTS public.icons_calls_connection;
DROP TABLE IF EXISTS public.images_calls_connection;
DROP TABLE IF EXISTS public.instructions_calls_connection;
DROP TABLE IF EXISTS public.items_calls_connection;
DROP TABLE IF EXISTS public.keys_calls_connection;
DROP TABLE IF EXISTS public.modalities_calls_connection;
DROP TABLE IF EXISTS public.models_calls_connection;
DROP TABLE IF EXISTS public.names_calls_connection;
DROP TABLE IF EXISTS public.objectives_calls_connection;
DROP TABLE IF EXISTS public.options_calls_connection;
DROP TABLE IF EXISTS public.parameter_fields_calls_connection;
DROP TABLE IF EXISTS public.parameters_calls_connection;
DROP TABLE IF EXISTS public.personas_calls_connection;
DROP TABLE IF EXISTS public.points_calls_connection;
DROP TABLE IF EXISTS public.pricing_calls_connection;
DROP TABLE IF EXISTS public.problem_statements_calls_connection;
DROP TABLE IF EXISTS public.profile_personas_calls_connection;
DROP TABLE IF EXISTS public.profiles_calls_connection;
DROP TABLE IF EXISTS public.prompts_calls_connection;
DROP TABLE IF EXISTS public.protocols_calls_connection;
DROP TABLE IF EXISTS public.provider_keys_calls_connection;
DROP TABLE IF EXISTS public.providers_calls_connection;
DROP TABLE IF EXISTS public.qualities_calls_connection;
DROP TABLE IF EXISTS public.questions_calls_connection;
DROP TABLE IF EXISTS public.reasoning_levels_calls_connection;
DROP TABLE IF EXISTS public.request_limits_calls_connection;
DROP TABLE IF EXISTS public.roles_calls_connection;
DROP TABLE IF EXISTS public.rubrics_calls_connection;
DROP TABLE IF EXISTS public.scenario_flags_calls_connection;
DROP TABLE IF EXISTS public.scenario_positions_calls_connection;
DROP TABLE IF EXISTS public.scenario_rubrics_calls_connection;
DROP TABLE IF EXISTS public.scenario_time_limits_calls_connection;
DROP TABLE IF EXISTS public.scenarios_calls_connection;
DROP TABLE IF EXISTS public.settings_calls_connection;
DROP TABLE IF EXISTS public.simulation_availability_calls_connection;
DROP TABLE IF EXISTS public.simulation_positions_calls_connection;
DROP TABLE IF EXISTS public.simulations_calls_connection;
DROP TABLE IF EXISTS public.slugs_calls_connection;
DROP TABLE IF EXISTS public.standard_groups_calls_connection;
DROP TABLE IF EXISTS public.standards_calls_connection;
DROP TABLE IF EXISTS public.temperature_levels_calls_connection;
DROP TABLE IF EXISTS public.texts_calls_connection;
DROP TABLE IF EXISTS public.thresholds_calls_connection;
DROP TABLE IF EXISTS public.values_calls_connection;
DROP TABLE IF EXISTS public.videos_calls_connection;
DROP TABLE IF EXISTS public.voices_calls_connection;

COMMIT;
