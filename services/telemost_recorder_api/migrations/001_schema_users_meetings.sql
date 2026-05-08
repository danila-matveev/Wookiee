-- 001_schema_users_meetings.sql
CREATE SCHEMA IF NOT EXISTS telemost;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "moddatetime";

CREATE TABLE telemost.users (
    telegram_id   bigint PRIMARY KEY,
    bitrix_id     text NOT NULL UNIQUE,
    name          text NOT NULL,
    short_name    text,
    is_active     boolean NOT NULL DEFAULT true,
    synced_at     timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE telemost.users ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON telemost.users FROM anon;

CREATE TABLE telemost.meetings (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source               text NOT NULL CHECK (source IN ('telegram','calendar')),
    source_event_id      text,
    triggered_by         bigint REFERENCES telemost.users(telegram_id),
    meeting_url          text NOT NULL,
    title                text,
    organizer_id         bigint REFERENCES telemost.users(telegram_id),
    invitees             jsonb NOT NULL DEFAULT '[]',
    scheduled_at         timestamptz,
    started_at           timestamptz,
    ended_at             timestamptz,
    duration_seconds     integer,
    status               text NOT NULL DEFAULT 'queued'
                          CHECK (status IN ('queued','recording','postprocessing','done','failed')),
    error                text,
    audio_path           text,
    audio_expires_at     timestamptz,
    raw_segments         jsonb,
    processed_paragraphs jsonb,
    speakers_map         jsonb,
    summary              jsonb,
    tags                 text[],
    notified_at          timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_meetings_status ON telemost.meetings(status);
CREATE INDEX idx_meetings_scheduled ON telemost.meetings(scheduled_at);
CREATE INDEX idx_meetings_source_event ON telemost.meetings(source_event_id)
    WHERE source_event_id IS NOT NULL;
CREATE INDEX idx_meetings_audio_expires ON telemost.meetings(audio_expires_at)
    WHERE audio_path IS NOT NULL;
CREATE UNIQUE INDEX idx_meetings_active_unique
    ON telemost.meetings (meeting_url)
    WHERE status IN ('queued','recording','postprocessing');

ALTER TABLE telemost.meetings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON telemost.meetings FROM anon;

CREATE TRIGGER meetings_updated_at BEFORE UPDATE ON telemost.meetings
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);
