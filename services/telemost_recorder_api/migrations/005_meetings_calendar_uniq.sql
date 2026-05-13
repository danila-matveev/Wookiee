-- 005_meetings_calendar_uniq.sql
-- Idempotency for the Bitrix calendar scheduler:
-- a calendar event can recur (same source_event_id, different scheduled_at,
-- e.g. daily Dayli), so the key includes scheduled_at. Partial — leaves the
-- manual `source='telegram'` row free of this constraint.
CREATE UNIQUE INDEX IF NOT EXISTS uniq_meetings_calendar_event_slot
    ON telemost.meetings (source, source_event_id, scheduled_at)
    WHERE source = 'calendar' AND source_event_id IS NOT NULL;
