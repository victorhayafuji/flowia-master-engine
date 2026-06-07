-- Migration: Supabase Auth Native RLS Integration
-- Description: Replaces `current_setting('app.current_org_id')` with native `auth.uid()` checks against the `dashboard_users` table to ensure the dashboard frontend can securely fetch tenant data without relying on custom Postgres session variables.

-- 1. Helper Functions to get user context securely
CREATE OR REPLACE FUNCTION public.get_auth_org_id()
RETURNS UUID
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
  SELECT organization_id 
  FROM public.dashboard_users 
  WHERE id = auth.uid()
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.get_auth_role()
RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
  SELECT role 
  FROM public.dashboard_users 
  WHERE id = auth.uid()
  LIMIT 1;
$$;

-- 2. Drop the old custom setting policies
-- Organizations
DROP POLICY IF EXISTS "org_read" ON organizations;
DROP POLICY IF EXISTS "org_update" ON organizations;
DROP POLICY IF EXISTS "org_insert" ON organizations;
DROP POLICY IF EXISTS "org_delete" ON organizations;

-- Other Tenant Tables
DROP POLICY IF EXISTS "tenant_read" ON professionals;
DROP POLICY IF EXISTS "tenant_insert" ON professionals;
DROP POLICY IF EXISTS "tenant_update" ON professionals;
DROP POLICY IF EXISTS "tenant_delete" ON professionals;

DROP POLICY IF EXISTS "tenant_read" ON service_catalog;
DROP POLICY IF EXISTS "tenant_insert" ON service_catalog;
DROP POLICY IF EXISTS "tenant_update" ON service_catalog;
DROP POLICY IF EXISTS "tenant_delete" ON service_catalog;

DROP POLICY IF EXISTS "tenant_read" ON patients;
DROP POLICY IF EXISTS "tenant_insert" ON patients;
DROP POLICY IF EXISTS "tenant_update" ON patients;
DROP POLICY IF EXISTS "tenant_delete" ON patients;

DROP POLICY IF EXISTS "tenant_read" ON appointments;
DROP POLICY IF EXISTS "tenant_insert" ON appointments;
DROP POLICY IF EXISTS "tenant_update" ON appointments;
DROP POLICY IF EXISTS "tenant_delete" ON appointments;

DROP POLICY IF EXISTS "tenant_read" ON reminders;
DROP POLICY IF EXISTS "tenant_insert" ON reminders;
DROP POLICY IF EXISTS "tenant_update" ON reminders;
DROP POLICY IF EXISTS "tenant_delete" ON reminders;

DROP POLICY IF EXISTS "tenant_read" ON anamnesis_templates;
DROP POLICY IF EXISTS "tenant_insert" ON anamnesis_templates;
DROP POLICY IF EXISTS "tenant_update" ON anamnesis_templates;
DROP POLICY IF EXISTS "tenant_delete" ON anamnesis_templates;

-- 3. Create new Native Auth Policies

-- Organizations
CREATE POLICY "org_read_native" ON organizations FOR SELECT USING (
    id = public.get_auth_org_id()
    OR public.get_auth_role() = 'super_admin'
);
CREATE POLICY "org_update_native" ON organizations FOR UPDATE USING (
    id = public.get_auth_org_id()
    OR public.get_auth_role() = 'super_admin'
);
CREATE POLICY "org_insert_native" ON organizations FOR INSERT WITH CHECK (
    public.get_auth_role() = 'super_admin'
);
CREATE POLICY "org_delete_native" ON organizations FOR DELETE USING (
    public.get_auth_role() = 'super_admin'
);

-- Template Function for other tenant tables using Auth Uid
CREATE OR REPLACE FUNCTION create_native_tenant_policies(table_name TEXT) RETURNS VOID AS $$
BEGIN
    EXECUTE format('
        CREATE POLICY "tenant_read_native" ON %I FOR SELECT USING (
            organization_id = public.get_auth_org_id()
            OR public.get_auth_role() = ''super_admin''
        );
        CREATE POLICY "tenant_insert_native" ON %I FOR INSERT WITH CHECK (
            organization_id = public.get_auth_org_id()
        );
        CREATE POLICY "tenant_update_native" ON %I FOR UPDATE USING (
            organization_id = public.get_auth_org_id()
            OR public.get_auth_role() = ''super_admin''
        );
        CREATE POLICY "tenant_delete_native" ON %I FOR DELETE USING (
            organization_id = public.get_auth_org_id()
            OR public.get_auth_role() = ''super_admin''
        );
    ', table_name, table_name, table_name, table_name);
END;
$$ LANGUAGE plpgsql;

-- Apply to all main tables
SELECT create_native_tenant_policies('professionals');
SELECT create_native_tenant_policies('service_catalog');
SELECT create_native_tenant_policies('patients');
SELECT create_native_tenant_policies('appointments');
SELECT create_native_tenant_policies('reminders');
SELECT create_native_tenant_policies('anamnesis_templates');

-- Cleanup setup function
DROP FUNCTION create_native_tenant_policies;
