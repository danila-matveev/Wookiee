-- 006_voice_trigger_candidates.sql
-- Persistence for voice-trigger candidates extracted by services/telemost_recorder_api/voice_triggers.py.
-- Each candidate is shown to the user with [✅ Создать] / [✏️ Поправить] / [❌ Игнор] buttons.
-- Phase 2 (T7) writes the candidate id into callback_data so the click can
-- resolve back to the original LLM-extracted fields hours after the meeting
-- summary was delivered.
--
-- Status transitions:
--   pending  → created  (user clicked ✅ Создать, Bitrix entity successfully created)
--   pending  → edited   (user opened inline edit form — Phase 2 placeholder)
--   pending  → ignored  (user clicked ❌ Игнор)
--
-- bitrix_id holds the Bitrix24 task id or calendar event id once status='created'.
-- extracted_fields is the JSONB blob returned by Stage 2 slot-filling
-- (per-intent shape — see voice_triggers.py prompts).
CREATE TABLE IF NOT EXISTS telemost.voice_trigger_candidates (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id        UUID REFERENCES telemost.meetings(id) ON DELETE CASCADE,
    intent            TEXT NOT NULL
                          CHECK (intent IN ('task','meeting','note','attention','reminder')),
    speaker           TEXT NOT NULL,
    raw_text          TEXT NOT NULL,
    extracted_fields  JSONB NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','created','edited','ignored')),
    bitrix_id         TEXT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vtc_meeting
    ON telemost.voice_trigger_candidates(meeting_id);

-- Standard Wookiee RLS template: enable RLS, lock anon role out entirely.
-- The API uses the service_role JWT (SUPABASE_SERVICE_KEY) which bypasses RLS.
ALTER TABLE telemost.voice_trigger_candidates ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON telemost.voice_trigger_candidates FROM anon;
