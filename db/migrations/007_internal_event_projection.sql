-- Durable internal event projection. External notification state is untouched.
BEGIN;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='wf_event_projector') THEN
    CREATE ROLE wf_event_projector NOLOGIN;
  END IF;
END $$;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_event_projector;

ALTER TABLE worthkind_flow.event_outbox ADD COLUMN projected_at timestamptz;
CREATE INDEX idx_wf_outbox_unprojected
  ON worthkind_flow.event_outbox(created_at,id) WHERE projected_at IS NULL;

CREATE TABLE worthkind_flow.case_activity (
  event_id uuid PRIMARY KEY REFERENCES worthkind_flow.event_outbox(id),
  property_id uuid NOT NULL,
  case_id uuid NOT NULL,
  event_type text NOT NULL,
  occurred_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id)
);
ALTER TABLE worthkind_flow.case_activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.case_activity FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.case_activity FROM PUBLIC;

CREATE FUNCTION worthkind_flow.project_case_events(p_limit integer)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_count integer;
BEGIN
  IF p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 500 THEN
    RAISE EXCEPTION 'Invalid event batch size' USING ERRCODE='22023';
  END IF;
  WITH picked AS MATERIALIZED (
    SELECT e.id,e.property_id,e.case_id,e.event_type,e.created_at
    FROM worthkind_flow.event_outbox e
    WHERE e.projected_at IS NULL
    ORDER BY e.created_at,e.id
    LIMIT p_limit FOR UPDATE SKIP LOCKED
  ), inserted AS (
    INSERT INTO worthkind_flow.case_activity(event_id,property_id,case_id,event_type,occurred_at)
    SELECT id,property_id,case_id,event_type,created_at FROM picked
    ON CONFLICT(event_id) DO NOTHING RETURNING event_id
  )
  UPDATE worthkind_flow.event_outbox e SET projected_at=clock_timestamp()
    FROM picked p WHERE e.id=p.id;
  GET DIAGNOSTICS v_count=ROW_COUNT;
  RETURN v_count;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.project_case_events(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.project_case_events(integer) TO wf_event_projector;
COMMIT;
