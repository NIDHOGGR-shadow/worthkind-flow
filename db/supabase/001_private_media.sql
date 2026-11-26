-- Supabase-specific infrastructure, separate from portable PostgreSQL migrations.
BEGIN;
CREATE SCHEMA worthkind_media_auth;
REVOKE ALL ON SCHEMA worthkind_media_auth FROM PUBLIC;
GRANT USAGE ON SCHEMA worthkind_media_auth TO authenticated;

-- A narrow boolean authorization oracle, never returns identity or membership records.
CREATE FUNCTION worthkind_media_auth.can_access(p_object_name text)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
 SELECT COALESCE(
   p_object_name ~ '^[a-z0-9][a-z0-9-]{1,99}/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|jpeg|png|webp)$'
   AND EXISTS(
      SELECT 1 FROM auth.users u JOIN auth.sessions s ON s.user_id=u.id
      WHERE u.id=auth.uid() AND NOT u.is_anonymous
        AND (u.email_confirmed_at IS NOT NULL OR u.phone_confirmed_at IS NOT NULL)
        AND s.id::text=auth.jwt()->>'session_id'
   )
   AND EXISTS(
      SELECT 1 FROM worthkind_flow.resolve_staff_session(auth.uid()::text,split_part(p_object_name,'/',1),'case:read') s
      WHERE s.membership_role IN ('owner','manager')
   ),false)
$$;
REVOKE ALL ON FUNCTION worthkind_media_auth.can_access(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_media_auth.can_access(text) TO authenticated;

INSERT INTO storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
VALUES('worthkind-flow-media','worthkind-flow-media',false,5242880,ARRAY['image/jpeg','image/png','image/webp']);

CREATE POLICY wf_media_staff_select ON storage.objects FOR SELECT TO authenticated
 USING(bucket_id='worthkind-flow-media' AND worthkind_media_auth.can_access(name));
CREATE POLICY wf_media_staff_insert ON storage.objects FOR INSERT TO authenticated
 WITH CHECK(bucket_id='worthkind-flow-media' AND worthkind_media_auth.can_access(name));
-- Future permissive policies must not widen this bucket to other tenants.
CREATE POLICY wf_media_auth_select_boundary ON storage.objects AS RESTRICTIVE FOR SELECT TO authenticated
 USING(CASE WHEN bucket_id='worthkind-flow-media' THEN worthkind_media_auth.can_access(name) ELSE true END);
CREATE POLICY wf_media_auth_insert_boundary ON storage.objects AS RESTRICTIVE FOR INSERT TO authenticated
 WITH CHECK(CASE WHEN bucket_id='worthkind-flow-media' THEN worthkind_media_auth.can_access(name) ELSE true END);
CREATE POLICY wf_media_auth_no_update ON storage.objects AS RESTRICTIVE FOR UPDATE TO authenticated
 USING(bucket_id<>'worthkind-flow-media') WITH CHECK(bucket_id<>'worthkind-flow-media');
CREATE POLICY wf_media_auth_no_delete ON storage.objects AS RESTRICTIVE FOR DELETE TO authenticated
 USING(bucket_id<>'worthkind-flow-media');
CREATE POLICY wf_media_anon_boundary ON storage.objects AS RESTRICTIVE FOR ALL TO anon
 USING(bucket_id<>'worthkind-flow-media') WITH CHECK(bucket_id<>'worthkind-flow-media');
COMMIT;
