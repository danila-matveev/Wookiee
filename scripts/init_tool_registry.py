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


SEED_TOOLS = [
    # Skills - analytics
    ("/finance-report", "Финансовый анализ", "skill", "analytics", "active", "v4",
     "P&L бренда WB+OZON, 12 секций, модельная декомпозиция, воронка, план-факт, callout-блоки. 3-волновой движок + 2 канальных аналитика + верификатор.",
     "/finance-report 2026-04-10", "danila"),
    ("/marketing-report", "Маркетинговый анализ", "skill", "analytics", "active", "v1",
     "Воронка трафика, ДРР по каналам, блогеры/ВК/SMM из Google Sheets, матрица эффективности моделей.",
     "/marketing-report 2026-04-10", "danila"),
    ("/funnel-report", "Анализ воронки WB", "skill", "analytics", "active", "v1",
     "Помодельная воронка WB: переходы→корзина→заказы→выкупы. CRO как главная метрика.",
     "/funnel-report 2026-04-10", "danila"),
    ("/analytics-report", "Мета-оркестратор аналитики", "skill", "analytics", "testing", "",
     "Вызывает finance + marketing + funnel последовательно.", "/analytics-report 2026-04-10", "danila"),
    ("/abc-audit", "ABC-аудит товарной матрицы", "skill", "analytics", "testing", "v1",
     "ABC x ROI классификация, color_code анализ, рекомендации по артикулам.", "/abc-audit", "danila"),
    ("/reviews-audit", "Аудит отзывов и возвратов", "skill", "analytics", "testing", "",
     "LLM-кластеризация отзывов/вопросов WB, модельные карточки, gap-анализ.", "/reviews-audit", "danila"),
    ("/market-review", "Обзор рынка и конкурентов", "skill", "analytics", "testing", "",
     "Ежемесячный анализ через MPStats: динамика категории, конкуренты.", "/market-review", "danila"),
    # Skills - planning
    ("/monthly-plan", "Месячный бизнес-план", "skill", "planning", "testing", "",
     "Multi-wave генерация бизнес-плана: таргеты, действия по моделям.", "/monthly-plan 2026-05", "danila"),
    # Skills - content
    ("/content-search", "Поиск фото бренда", "skill", "content", "testing", "",
     "Vector search по Content KB (~10K фото). Подбор контента под воронку.", "/content-search модель на пляже", "danila"),
    # Skills - team
    ("/bitrix-task", "Задачи в Битрикс24", "skill", "team", "active", "",
     "Создание задач через Битрикс24 REST API.", "поставь задачу ...", "danila"),
    ("/bitrix-analytics", "Пульс команды Битрикс", "skill", "team", "active", "",
     "Еженедельный отчёт по активности в Битрикс24: чаты, задачи, блокеры.", "/bitrix-analytics", "danila"),
    ("/finolog", "ДДС операции Финолог", "skill", "infra", "active", "",
     "Расходы, переводы, сводка по счетам, прогноз кассового разрыва.", "запиши расход ...", "danila"),
    # Services
    ("sheets-sync", "Синхронизация Google Sheets", "service", "infra", "active", "",
     "WB/OZON/МойСклад → Google Sheets. Остатки, цены, отзывы, финансы.",
     "python -m services.sheets_sync.runner all", "danila"),
    ("content-kb", "Индексатор фото (Content KB)", "service", "content", "active", "",
     "YaDisk → Gemini Embedding → pgvector. ~10K изображений.",
     "python -m services.content_kb.scripts.index_all", "danila"),
    ("logistics-audit", "Аудит логистики WB", "service", "analytics", "active", "",
     "Расчёт переплаты за логистику по формуле Оферты. Excel 11 листов.",
     "python -m services.logistics_audit.runner OOO 2026-01-01 2026-03-23", "danila"),
    ("wb-localization", "Оптимизация ИЛ/ИРП", "service", "infra", "active", "",
     "Калькулятор индекса локализации WB. Оптимальные склады для перемещения.",
     "python services/wb_localization/run_localization.py --cabinet ooo", "danila"),
    ("dashboard-api", "API WookieeHub", "service", "infra", "active", "",
     "FastAPI: ABC, Finance, Promo, Series, Stocks, Traffic, Comms.",
     "uvicorn services.dashboard_api.app:app --reload", "danila"),
    # Scripts
    ("collect-all", "Сборщик данных для аналитики", "script", "analytics", "active", "",
     "Параллельная загрузка: WB, OZON, Sheets → JSON (8 блоков).",
     "python scripts/analytics_report/collect_all.py --start DATE --end DATE", "danila"),
    ("sync-sheets-to-supabase", "Google Sheets → Supabase", "script", "infra", "active", "",
     "Синхронизация товарной матрицы: statusy, modeli, artikuly, tovary.",
     "python scripts/sync_sheets_to_supabase.py --level all", "danila"),
    ("abc-analysis", "ABC-анализ по финансам", "script", "analytics", "active", "",
     "Классификация артикулов: Лучшие/Хорошие/Неликвид/Новый.",
     "python scripts/abc_analysis.py --channel wb --save", "danila"),
    ("calc-irp", "Калькулятор ИЛ/ИРП", "script", "infra", "active", "",
     "ИЛ и ИРП для WB за 13 недель. Коэффициенты КТР/КРП.",
     "python scripts/calc_irp.py --top 20", "danila"),
    ("search-queries-sync", "Синхронизация поисковых запросов WB", "script", "analytics", "active", "",
     "Еженедельная загрузка аналитики поисковых запросов WB в Google Sheets. Cron: пн 10:00 МСК.",
     "python scripts/run_search_queries_sync.py", "danila"),
    ("sync-product-db", "Синхронизация товарной БД", "script", "infra", "active", "",
     "Google Sheets → Supabase: statusy, modeli, artikuly, tovary. Cron ежедневно 06:00 МСК.",
     "python scripts/sync_sheets_to_supabase.py --level all", "danila"),
]


def main():
    conn = _get_connection()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(DDL)
    cur.close()
    conn.close()
    print("✅ Tables created: tools, tool_runs")


def seed_tools() -> None:
    """Insert initial tool registry data (upsert)."""
    conn = _get_connection()
    conn.autocommit = True
    cur = conn.cursor()

    for slug, name, typ, cat, status, ver, desc, cmd, owner in SEED_TOOLS:
        cur.execute(
            """INSERT INTO tools (slug, display_name, type, category, status, version,
                description, run_command, owner)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                description = EXCLUDED.description,
                status = EXCLUDED.status,
                version = EXCLUDED.version,
                run_command = EXCLUDED.run_command,
                updated_at = now()""",
            (slug, name, typ, cat, status, ver or None, desc, cmd, owner),
        )

    cur.close()
    conn.close()
    print(f"✅ Seeded {len(SEED_TOOLS)} tools")


if __name__ == "__main__":
    import sys
    if "--seed-only" in sys.argv:
        seed_tools()
    else:
        main()
        seed_tools()
