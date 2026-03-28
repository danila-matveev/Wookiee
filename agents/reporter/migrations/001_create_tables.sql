-- agents/reporter/migrations/001_create_tables.sql
-- Reporter V4 Supabase tables

-- ── Report Runs ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS report_runs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    report_date DATE NOT NULL,
    report_type TEXT NOT NULL,
    scope_hash TEXT NOT NULL,
    scope_json JSONB NOT NULL,
    status TEXT DEFAULT 'pending',
    attempt INT DEFAULT 1,
    notion_url TEXT,
    telegram_message_id BIGINT,
    telegram_chat_id BIGINT,
    confidence FLOAT,
    cost_usd FLOAT,
    duration_sec FLOAT,
    issues JSONB,
    error TEXT,
    llm_model TEXT,
    llm_tokens_in INT,
    llm_tokens_out INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(report_date, report_type, scope_hash)
);

ALTER TABLE report_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON report_runs FOR ALL TO postgres USING (true);
CREATE POLICY "authenticated_read" ON report_runs FOR SELECT TO authenticated USING (true);

-- ── Analytics Rules (Playbook) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics_rules (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    rule_text TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    confidence FLOAT,
    evidence TEXT,
    report_types TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT
);

ALTER TABLE analytics_rules ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON analytics_rules FOR ALL TO postgres USING (true);
CREATE POLICY "authenticated_read" ON analytics_rules FOR SELECT TO authenticated USING (true);

-- ── Notification Log ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notification_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    notification_key TEXT NOT NULL UNIQUE,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    telegram_message_id BIGINT
);

ALTER TABLE notification_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON notification_log FOR ALL TO postgres USING (true);
