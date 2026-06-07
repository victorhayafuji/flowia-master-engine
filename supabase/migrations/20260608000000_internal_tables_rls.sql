-- Internal / backend-only tables: block PostgREST anon & authenticated.
-- No policies = deny by default. service_role + postgres direct still work.

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'webhook_message_dedup',
    'checkpoints',
    'checkpoint_blobs',
    'checkpoint_writes',
    'checkpoint_migrations'
  ] LOOP
    IF to_regclass('public.' || t) IS NOT NULL THEN
      EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
      EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated', t);
    END IF;
  END LOOP;
END $$;
