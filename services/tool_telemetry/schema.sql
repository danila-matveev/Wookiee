-- Agent Registry — tracks all agents, their versions, and prompt history
CREATE TABLE IF NOT EXISTS agent_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,
    agent_type TEXT NOT NULL CHECK (agent_type IN ('orchestrator', 'micro-agent')),
    version TEXT NOT NULL,
    md_file_path TEXT,
    system_prompt TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    mcp_tools TEXT[],
    model_tier TEXT CHECK (model_tier IN ('HEAVY', 'MAIN', 'LIGHT')),
    default_model TEXT,
    description TEXT,
    changelog TEXT,
    created_by TEXT DEFAULT 'auto-detect',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(agent_name, version)
);

CREATE INDEX IF NOT EXISTS idx_agent_registry_name ON agent_registry(agent_name, is_active);
CREATE INDEX IF NOT EXISTS idx_agent_registry_hash ON agent_registry(prompt_hash);

-- Agent Runs — every invocation of every agent
CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,
    parent_run_id UUID,
    agent_name TEXT NOT NULL,
    agent_type TEXT NOT NULL CHECK (agent_type IN ('orchestrator', 'micro-agent')),
    agent_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'timeout', 'skipped', 'running')),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    error_message TEXT,
    model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd NUMERIC(10,6),
    llm_calls INTEGER,
    tool_calls INTEGER,
    system_prompt_hash TEXT,
    user_input TEXT,
    output_summary TEXT,
    artifact JSONB,
    task_type TEXT,
    trigger TEXT CHECK (trigger IN ('cron', 'user_telegram', 'user_cli', 'orchestrator', 'manual')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_run_id ON agent_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_version ON agent_runs(agent_name, agent_version);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_date ON agent_runs(started_at DESC);

-- Orchestrator Run Summary — high-level view per pipeline execution
CREATE TABLE IF NOT EXISTS orchestrator_runs (
    run_id UUID PRIMARY KEY,
    orchestrator TEXT NOT NULL,
    orchestrator_version TEXT NOT NULL,
    task_type TEXT NOT NULL,
    trigger TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed', 'running')),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    agents_called INTEGER DEFAULT 0,
    agents_succeeded INTEGER DEFAULT 0,
    agents_failed INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd NUMERIC(10,6) DEFAULT 0,
    report_format TEXT,
    delivered_to TEXT[],
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_orchestrator_runs_date ON orchestrator_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_orchestrator_runs_status ON orchestrator_runs(status);

-- RLS policies (Supabase requirement per AGENTS.md)
ALTER TABLE agent_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE orchestrator_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_agent_registry" ON agent_registry FOR ALL USING (true);
CREATE POLICY "service_role_all_agent_runs" ON agent_runs FOR ALL USING (true);
CREATE POLICY "service_role_all_orchestrator_runs" ON orchestrator_runs FOR ALL USING (true);
