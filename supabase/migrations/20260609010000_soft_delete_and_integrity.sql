-- Soft-delete convention + data integrity hardening.

-- 1. Soft delete for patients (other core tables already have is_active).
ALTER TABLE patients ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
CREATE INDEX IF NOT EXISTS idx_pat_org_active ON patients(organization_id) WHERE is_active;

-- 2. No duplicate active service name per org (case-insensitive).
CREATE UNIQUE INDEX IF NOT EXISTS uq_svc_org_name_active
  ON service_catalog(organization_id, lower(name)) WHERE is_active;

-- 3. Protect organizations from accidental cascade wipe.
--    Business tables: organization_id FK CASCADE -> RESTRICT (org is soft-deleted only).
DO $$
DECLARE
  t text;
  fk text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'patients',
    'appointments',
    'professionals',
    'service_catalog',
    'reminders',
    'anamnesis_templates',
    'anamnesis_responses'
  ] LOOP
    fk := t || '_organization_id_fkey';
    IF EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname = fk AND conrelid = ('public.' || t)::regclass
    ) THEN
      EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT %I', t, fk);
    END IF;
    EXECUTE format(
      'ALTER TABLE public.%I ADD CONSTRAINT %I '
      'FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE RESTRICT',
      t, fk
    );
  END LOOP;
END $$;
