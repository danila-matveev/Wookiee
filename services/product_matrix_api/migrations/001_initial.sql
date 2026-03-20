-- services/product_matrix_api/migrations/001_initial.sql
-- Creates new tables and hub schema for Product Matrix Editor.
-- Run against Supabase PostgreSQL.

-- Hub schema
CREATE SCHEMA IF NOT EXISTS hub;

-- field_definitions
CREATE TABLE IF NOT EXISTS field_definitions (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    field_type VARCHAR(30) NOT NULL
        CHECK (field_type IN (
            'text', 'number', 'select', 'multi_select', 'file',
            'url', 'relation', 'date', 'checkbox', 'formula', 'rollup'
        )),
    config JSONB DEFAULT '{}',
    section VARCHAR(100),
    sort_order INT DEFAULT 0,
    is_system BOOLEAN DEFAULT FALSE,
    is_visible BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(entity_type, field_name)
);

-- sertifikaty
CREATE TABLE IF NOT EXISTS sertifikaty (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(200) NOT NULL,
    tip VARCHAR(100),
    nomer VARCHAR(100),
    data_vydachi DATE,
    data_okonchaniya DATE,
    organ_sertifikacii VARCHAR(200),
    file_url TEXT,
    gruppa_sertifikata VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- modeli_osnova_sertifikaty (M2M)
CREATE TABLE IF NOT EXISTS modeli_osnova_sertifikaty (
    model_osnova_id INT REFERENCES modeli_osnova(id) ON DELETE CASCADE,
    sertifikat_id INT REFERENCES sertifikaty(id) ON DELETE CASCADE,
    PRIMARY KEY (model_osnova_id, sertifikat_id)
);

-- archive_records
CREATE TABLE IF NOT EXISTS archive_records (
    id SERIAL PRIMARY KEY,
    original_table VARCHAR(50) NOT NULL,
    original_id INT NOT NULL,
    full_record JSONB NOT NULL,
    related_records JSONB DEFAULT '[]',
    deleted_by VARCHAR(100),
    deleted_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '30 days'),
    restore_available BOOLEAN DEFAULT TRUE
);

-- hub.users
CREATE TABLE IF NOT EXISTS hub.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(200) UNIQUE NOT NULL,
    name VARCHAR(200),
    role VARCHAR(20) NOT NULL DEFAULT 'viewer'
        CHECK (role IN ('viewer', 'editor', 'admin')),
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- hub.audit_log
CREATE TABLE IF NOT EXISTS hub.audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    user_id INT REFERENCES hub.users(id),
    user_email VARCHAR(200),
    action VARCHAR(30) NOT NULL
        CHECK (action IN (
            'create', 'update', 'delete', 'bulk_update',
            'bulk_delete', 'restore', 'login', 'export'
        )),
    entity_type VARCHAR(50),
    entity_id INT,
    entity_name VARCHAR(200),
    changes JSONB,
    ip_address INET,
    user_agent TEXT,
    request_id UUID,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON hub.audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON hub.audit_log(entity_type, entity_id);

-- hub.saved_views
CREATE TABLE IF NOT EXISTS hub.saved_views (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES hub.users(id),
    entity_type VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    config JSONB NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- hub.ui_preferences
CREATE TABLE IF NOT EXISTS hub.ui_preferences (
    user_id INT PRIMARY KEY REFERENCES hub.users(id),
    sidebar_collapsed BOOLEAN DEFAULT FALSE,
    theme VARCHAR(10) DEFAULT 'dark',
    column_widths JSONB DEFAULT '{}',
    sidebar_order JSONB DEFAULT '[]',
    recent_entities JSONB DEFAULT '[]',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- RLS
ALTER TABLE field_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sertifikaty ENABLE ROW LEVEL SECURITY;
ALTER TABLE modeli_osnova_sertifikaty ENABLE ROW LEVEL SECURITY;
ALTER TABLE archive_records ENABLE ROW LEVEL SECURITY;

-- Insert default anonymous user for testing
INSERT INTO hub.users (email, name, role) VALUES ('anonymous', 'Anonymous', 'admin')
ON CONFLICT (email) DO NOTHING;
