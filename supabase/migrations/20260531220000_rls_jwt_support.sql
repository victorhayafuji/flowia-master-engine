-- Fix RLS policies to support both backend setting (app.xyz) and frontend JWT (auth.jwt())

CREATE OR REPLACE FUNCTION public.get_user_role() RETURNS TEXT AS $$
BEGIN
    RETURN COALESCE(
        current_setting('app.user_role', true),
        auth.jwt()->'user_metadata'->>'role'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.get_org_id() RETURNS UUID AS $$
DECLARE
    org_val TEXT;
BEGIN
    org_val := COALESCE(
        current_setting('app.current_org_id', true),
        auth.jwt()->'user_metadata'->>'org_id'
    );
    IF org_val = '' OR org_val IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN org_val::UUID;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- organizations policies (super_admin has full access, org_admin can read/update their own)
DROP POLICY IF EXISTS "org_read" ON organizations;
CREATE POLICY "org_read" ON organizations FOR SELECT USING (
    id = public.get_org_id()
    OR public.get_user_role() = 'super_admin'
);

DROP POLICY IF EXISTS "org_update" ON organizations;
CREATE POLICY "org_update" ON organizations FOR UPDATE USING (
    id = public.get_org_id()
    OR public.get_user_role() = 'super_admin'
);

DROP POLICY IF EXISTS "org_insert" ON organizations;
CREATE POLICY "org_insert" ON organizations FOR INSERT WITH CHECK (
    public.get_user_role() = 'super_admin'
);

DROP POLICY IF EXISTS "org_delete" ON organizations;
CREATE POLICY "org_delete" ON organizations FOR DELETE USING (
    public.get_user_role() = 'super_admin'
);

-- Template for other tenant-specific tables
CREATE OR REPLACE FUNCTION create_tenant_policies_v2(table_name TEXT) RETURNS VOID AS $$
BEGIN
    EXECUTE format('
        DROP POLICY IF EXISTS "tenant_read" ON %I;
        CREATE POLICY "tenant_read" ON %I FOR SELECT USING (
            organization_id = public.get_org_id()
            OR public.get_user_role() = ''super_admin''
        );

        DROP POLICY IF EXISTS "tenant_insert" ON %I;
        CREATE POLICY "tenant_insert" ON %I FOR INSERT WITH CHECK (
            organization_id = public.get_org_id()
        );

        DROP POLICY IF EXISTS "tenant_update" ON %I;
        CREATE POLICY "tenant_update" ON %I FOR UPDATE USING (
            organization_id = public.get_org_id()
            OR public.get_user_role() = ''super_admin''
        );

        DROP POLICY IF EXISTS "tenant_delete" ON %I;
        CREATE POLICY "tenant_delete" ON %I FOR DELETE USING (
            organization_id = public.get_org_id()
            OR public.get_user_role() = ''super_admin''
        );
    ', table_name, table_name, table_name, table_name, table_name, table_name, table_name, table_name, table_name);
END;
$$ LANGUAGE plpgsql;

SELECT create_tenant_policies_v2('professionals');
SELECT create_tenant_policies_v2('service_catalog');
SELECT create_tenant_policies_v2('patients');
SELECT create_tenant_policies_v2('appointments');
SELECT create_tenant_policies_v2('reminders');
SELECT create_tenant_policies_v2('anamnesis_templates');
SELECT create_tenant_policies_v2('dashboard_users');
SELECT create_tenant_policies_v2('conversation_metrics');
SELECT create_tenant_policies_v2('knowledge_chunks');
SELECT create_tenant_policies_v2('knowledge_gaps');
SELECT create_tenant_policies_v2('docs_bronze');
SELECT create_tenant_policies_v2('docs_silver');
SELECT create_tenant_policies_v2('docs_gold_vectors');

DROP FUNCTION create_tenant_policies_v2;
