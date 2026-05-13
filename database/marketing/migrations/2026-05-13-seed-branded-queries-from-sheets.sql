-- Seed crm.branded_queries with 25 brand search words from the Google Sheets master list
-- ("Аналитика по запросам" worksheet, "Назначение" = "брендированный запрос" rows).
--
-- Why this seed is needed:
--   After view v2 + RPC v3 landed (B.0.1 + R.1.1), brand metrics still showed zeros in the UI
--   because crm.branded_queries was empty — the new view sources brand entries from this
--   CRM table, not from the Sheets master list directly. The Sheets master is owned by
--   the operator; the CRM table is the system-of-record for the Hub UI.
--
-- Effect of this seed:
--   22 of these 25 words already have 1-52 weeks of WB metrics in marketing.search_queries_weekly
--   (e.g. 'wooki' has 12 months of history → 11.9M frequency / 589K transitions / 10.5K orders).
--   After this seed runs, those metrics flow through to the Hub UI's "Брендированные запросы" group.
--   The remaining 3 words (мияфул, Alice, элис) currently have no weekly data — they'll
--   show zeros until WB starts reporting their search volume.
--
-- Idempotent: re-running is a no-op (ON CONFLICT DO NOTHING). Applied to prod as
-- migration `marketing_seed_branded_queries_from_sheets` on 2026-05-13.

INSERT INTO crm.branded_queries (query, canonical_brand, status)
VALUES
  ('wooki',   'Wookiee', 'active'),
  ('Вуки',    'Wookiee', 'active'),
  ('wookei',  'Wookiee', 'active'),
  ('wokie',   'Wookiee', 'active'),
  ('Vuki',    'Wookiee', 'active'),
  ('Moon',    'Wookiee', 'active'),
  ('Мун',     'Wookiee', 'active'),
  ('Ruby',    'Wookiee', 'active'),
  ('руби',    'Wookiee', 'active'),
  ('Joy',     'Wookiee', 'active'),
  ('джой',    'Wookiee', 'active'),
  ('Audrey',  'Wookiee', 'active'),
  ('одри',    'Wookiee', 'active'),
  ('Wendy',   'Wookiee', 'active'),
  ('венди',   'Wookiee', 'active'),
  ('Miafull', 'Wookiee', 'active'),
  ('мияфул',  'Wookiee', 'active'),
  ('Bella',   'Wookiee', 'active'),
  ('белла',   'Wookiee', 'active'),
  ('Lana',    'Wookiee', 'active'),
  ('лана',    'Wookiee', 'active'),
  ('Valery',  'Wookiee', 'active'),
  ('валери',  'Wookiee', 'active'),
  ('Alice',   'Wookiee', 'active'),
  ('элис',    'Wookiee', 'active')
ON CONFLICT DO NOTHING;
