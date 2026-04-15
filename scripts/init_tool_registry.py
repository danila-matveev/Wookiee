#!/usr/bin/env python3
"""Create tool registry tables in Supabase."""
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv("sku_database/.env")


def _get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "postgres"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


DDL = """
CREATE TABLE IF NOT EXISTS tools (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  slug            text UNIQUE NOT NULL,
  display_name    text NOT NULL,
  type            text NOT NULL CHECK (type IN ('skill', 'script', 'service')),
  category        text CHECK (category IN ('analytics', 'planning', 'content', 'team', 'infra')),
  description     text,
  how_it_works    text,
  status          text DEFAULT 'active' CHECK (status IN ('active', 'testing', 'deprecated')),
  version         text,
  run_command     text,
  data_sources    text[],
  depends_on      text[],
  output_targets  text[],
  owner           text,
  total_runs      int DEFAULT 0,
  success_rate    float DEFAULT 0,
  avg_duration    float DEFAULT 0,
  last_run_at     timestamptz,
  last_status     text,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tool_runs (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  tool_slug       text NOT NULL REFERENCES tools(slug),
  tool_version    text,
  started_at      timestamptz DEFAULT now(),
  finished_at     timestamptz,
  duration_sec    float,
  status          text NOT NULL CHECK (status IN ('running', 'success', 'error', 'timeout', 'data_not_ready')),
  trigger_type    text,
  triggered_by    text,
  environment     text,
  period_start    date,
  period_end      date,
  depth           text,
  result_url      text,
  error_message   text,
  error_stage     text,
  items_processed int,
  output_sections int,
  details         jsonb,
  model_used      text,
  tokens_input    int,
  tokens_output   int,
  notes           text
);

CREATE INDEX IF NOT EXISTS idx_tool_runs_slug ON tool_runs(tool_slug);
CREATE INDEX IF NOT EXISTS idx_tool_runs_started ON tool_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_runs_status ON tool_runs(status);
"""


def main():
    conn = _get_connection()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(DDL)
    cur.close()
    conn.close()
    print("✅ Tables created: tools, tool_runs")


if __name__ == "__main__":
    main()
