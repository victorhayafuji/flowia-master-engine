-- Auto-update updated_at on row changes (was static at insert time).

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END $$;

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'organizations',
    'patients',
    'appointments',
    'docs_bronze',
    'anamnesis_responses'
  ] LOOP
    IF to_regclass('public.' || t) IS NOT NULL THEN
      EXECUTE format('DROP TRIGGER IF EXISTS trg_set_updated_at ON public.%I', t);
      EXECUTE format(
        'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.%I '
        'FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t
      );
    END IF;
  END LOOP;
END $$;
