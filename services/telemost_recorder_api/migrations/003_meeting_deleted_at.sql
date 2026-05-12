-- 003_meeting_deleted_at.sql
ALTER TABLE telemost.meetings
    ADD COLUMN deleted_at timestamptz;

CREATE INDEX idx_meetings_not_deleted
    ON telemost.meetings(triggered_by)
    WHERE deleted_at IS NULL;
