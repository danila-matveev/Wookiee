-- Task 3.1 — `marketing.sync_log`: журнал ETL запусков для observability + UpdateBar.
-- ETL hooks (Python) — отдельный backlog (Task 3.1 Step 2-3); таблица создаётся сейчас,
-- UpdateBar показывает "—" до появления первой строки.
-- RLS: authenticated SELECT (UI читает), service_role full (ETL пишет).

CREATE TABLE marketing.sync_log (
  id              bigserial PRIMARY KEY,
  job_name        text NOT NULL,
  status          text NOT NULL CHECK (status IN ('running', 'success', 'failed')),
  started_at      timestamptz NOT NULL DEFAULT now(),
  finished_at     timestamptz,
  rows_processed  integer,
  rows_written    integer,
  weeks_covered   text,
  error_message   text,
  triggered_by    text
);

CREATE INDEX idx_sync_log_job_finished ON marketing.sync_log(job_name, finished_at DESC);

ALTER TABLE marketing.sync_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY sl_read ON marketing.sync_log
  FOR SELECT TO authenticated
  USING (true);

GRANT SELECT ON marketing.sync_log TO authenticated;
GRANT ALL    ON marketing.sync_log TO service_role;
GRANT USAGE  ON SEQUENCE marketing.sync_log_id_seq TO service_role;

COMMENT ON TABLE marketing.sync_log IS
  'Журнал ETL-синхронизаций (sheets_sync). UpdateBar читает последнюю запись по job_name. ETL hooks deferred — см. Task 3.1 Step 2.';
