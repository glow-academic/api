-- Change args_outputs_resource unique constraint from (args_id, name) to (args_id, name, template)
-- to allow multiple routing entries (e.g. artifact_attempt, artifact_persona) that share
-- the same args_id and name but differ in template value.

ALTER TABLE args_outputs_resource
  DROP CONSTRAINT IF EXISTS args_outputs_resource_args_id_name_key;

ALTER TABLE args_outputs_resource
  ADD CONSTRAINT args_outputs_resource_args_id_name_template_key UNIQUE (args_id, name, template);
