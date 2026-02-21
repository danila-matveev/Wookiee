-- ============================================================================
-- Людмила 2.0 — таблицы памяти (Supabase PostgreSQL)
-- ============================================================================
-- Запуск: python lyudmila_bot/database/deploy.py
-- ============================================================================

-- 1. Сотрудники (синхронизация из Bitrix24)
CREATE TABLE IF NOT EXISTS lyudmila_employees (
    id SERIAL PRIMARY KEY,
    bitrix_id INTEGER UNIQUE NOT NULL,
    first_name TEXT,
    last_name TEXT,
    full_name TEXT,
    email TEXT,
    position TEXT,
    department_ids INTEGER[] DEFAULT '{}',
    is_internal BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    custom_role TEXT,
    synced_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lyudmila_employees_bitrix_id ON lyudmila_employees(bitrix_id);
CREATE INDEX IF NOT EXISTS idx_lyudmila_employees_internal ON lyudmila_employees(is_internal) WHERE is_active = true;

-- 2. Задачи (синхронизация из Bitrix24, последние 6 мес.)
CREATE TABLE IF NOT EXISTS lyudmila_tasks (
    id SERIAL PRIMARY KEY,
    bitrix_task_id INTEGER UNIQUE NOT NULL,
    title TEXT,
    description TEXT,
    status INTEGER,
    priority INTEGER,
    responsible_id INTEGER,
    created_by INTEGER,
    deadline TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    auditors INTEGER[] DEFAULT '{}',
    accomplices INTEGER[] DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lyudmila_tasks_bitrix_id ON lyudmila_tasks(bitrix_task_id);
CREATE INDEX IF NOT EXISTS idx_lyudmila_tasks_responsible ON lyudmila_tasks(responsible_id);
CREATE INDEX IF NOT EXISTS idx_lyudmila_tasks_created_by ON lyudmila_tasks(created_by);
CREATE INDEX IF NOT EXISTS idx_lyudmila_tasks_deadline ON lyudmila_tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_lyudmila_tasks_status ON lyudmila_tasks(status);

-- 3. Комментарии к задачам
CREATE TABLE IF NOT EXISTS lyudmila_task_comments (
    id SERIAL PRIMARY KEY,
    bitrix_task_id INTEGER NOT NULL,
    author_id INTEGER,
    comment_text TEXT,
    created_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lyudmila_comments_task ON lyudmila_task_comments(bitrix_task_id);
CREATE INDEX IF NOT EXISTS idx_lyudmila_comments_author ON lyudmila_task_comments(author_id);

-- 4. Подсказки Людмилы (трекинг принятия/отклонения)
CREATE TABLE IF NOT EXISTS lyudmila_suggestions (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    entity_type TEXT NOT NULL,
    suggestion_text TEXT NOT NULL,
    suggestion_type TEXT,
    accepted BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lyudmila_suggestions_tg ON lyudmila_suggestions(telegram_id);

-- 5. Предпочтения пользователей
CREATE TABLE IF NOT EXISTS lyudmila_user_preferences (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    preference_key TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(telegram_id, preference_key)
);

CREATE INDEX IF NOT EXISTS idx_lyudmila_prefs_tg ON lyudmila_user_preferences(telegram_id);

-- ============================================================================
-- RLS — Row Level Security
-- ============================================================================
ALTER TABLE lyudmila_employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE lyudmila_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE lyudmila_task_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE lyudmila_suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE lyudmila_user_preferences ENABLE ROW LEVEL SECURITY;

-- anon = 0 прав
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'lyudmila_employees' AND policyname = 'lyudmila_employees_anon_deny') THEN
        EXECUTE 'CREATE POLICY lyudmila_employees_anon_deny ON lyudmila_employees FOR ALL TO anon USING (false)';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'lyudmila_tasks' AND policyname = 'lyudmila_tasks_anon_deny') THEN
        EXECUTE 'CREATE POLICY lyudmila_tasks_anon_deny ON lyudmila_tasks FOR ALL TO anon USING (false)';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'lyudmila_task_comments' AND policyname = 'lyudmila_task_comments_anon_deny') THEN
        EXECUTE 'CREATE POLICY lyudmila_task_comments_anon_deny ON lyudmila_task_comments FOR ALL TO anon USING (false)';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'lyudmila_suggestions' AND policyname = 'lyudmila_suggestions_anon_deny') THEN
        EXECUTE 'CREATE POLICY lyudmila_suggestions_anon_deny ON lyudmila_suggestions FOR ALL TO anon USING (false)';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'lyudmila_user_preferences' AND policyname = 'lyudmila_user_preferences_anon_deny') THEN
        EXECUTE 'CREATE POLICY lyudmila_user_preferences_anon_deny ON lyudmila_user_preferences FOR ALL TO anon USING (false)';
    END IF;
END $$;

-- postgres (service_role) = полный доступ (по умолчанию обходит RLS как суперюзер)
