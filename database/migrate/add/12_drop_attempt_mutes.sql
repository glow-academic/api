-- Drop attempt_mutes — mute was removed (client controls mic by not sending speak)
DROP MATERIALIZED VIEW IF EXISTS public.attempt_mutes_mv;
DROP TABLE IF EXISTS public.attempt_mutes_entry CASCADE;
