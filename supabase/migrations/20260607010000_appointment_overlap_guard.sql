-- Prevent double-booking same professional at overlapping times (DB-level guard)
-- tstzrange() on timestamptz is not IMMUTABLE; use UTC-normalized tsrange helper.

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE OR REPLACE FUNCTION appointment_slot_range(p_start timestamptz, p_mins integer)
RETURNS tsrange
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
  SELECT tsrange(
    (p_start AT TIME ZONE 'UTC')::timestamp,
    ((p_start AT TIME ZONE 'UTC') + make_interval(mins => p_mins))::timestamp,
    '[)'
  );
$$;

ALTER TABLE appointments
  ADD CONSTRAINT appointments_no_overlap
  EXCLUDE USING gist (
    professional_id WITH =,
    appointment_slot_range(scheduled_at, duration_minutes) WITH &&
  )
  WHERE (status NOT IN ('cancelled', 'no_show'));
