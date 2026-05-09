-- 002_processed_calendar_events.sql (Phase 0 prepares the table, Phase 1 will write to it)
CREATE TABLE telemost.processed_calendar_events (
    bitrix_event_id  text PRIMARY KEY,
    meeting_id       uuid REFERENCES telemost.meetings(id) ON DELETE CASCADE,
    processed_at     timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE telemost.processed_calendar_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON telemost.processed_calendar_events FROM anon;
