-- Migration 005: Fix FieldDefinition alignment with ModelOsnovaUpdate schema
-- Phase 02-05: Backend fixes for Phase 2 UAT gaps (GAP-01)
--
-- Problem: field_name values in field_definitions don't match ModelOsnovaUpdate
-- Pydantic schema fields, causing edits to silently fail.
--
-- Uses field_name + entity_type WHERE clauses (not hardcoded IDs) for safety.

BEGIN;

-- 1. Rename mismatched fields to match actual DB columns / Pydantic schema
UPDATE field_definitions SET field_name = 'nazvanie_sayt', display_name = 'Название (сайт)'
  WHERE entity_type = 'modeli_osnova' AND field_name = 'nazvanie';

UPDATE field_definitions SET field_name = 'sostav_syrya', display_name = 'Состав сырья'
  WHERE entity_type = 'modeli_osnova' AND field_name = 'sostav';

UPDATE field_definitions SET field_name = 'razmery_modeli', field_type = 'text', display_name = 'Размеры модели'
  WHERE entity_type = 'modeli_osnova' AND field_name = 'razmer_id';

UPDATE field_definitions SET field_name = 'ves_kg', display_name = 'Вес (кг)'
  WHERE entity_type = 'modeli_osnova' AND field_name = 'ves_g';

UPDATE field_definitions SET field_name = 'dlina_cm', display_name = 'Длина (см)'
  WHERE entity_type = 'modeli_osnova' AND field_name = 'dlina_sm';

UPDATE field_definitions SET field_name = 'shirina_cm', display_name = 'Ширина (см)'
  WHERE entity_type = 'modeli_osnova' AND field_name = 'shirina_sm';

UPDATE field_definitions SET field_name = 'vysota_cm', display_name = 'Высота (см)'
  WHERE entity_type = 'modeli_osnova' AND field_name = 'vysota_sm';

UPDATE field_definitions SET field_name = 'tnved', display_name = 'ТНВЭД'
  WHERE entity_type = 'modeli_osnova' AND field_name = 'hs_code';

UPDATE field_definitions SET field_name = 'opisanie_sayt', display_name = 'Описание (сайт)'
  WHERE entity_type = 'modeli_osnova' AND field_name = 'opisanie';

-- 2. Delete phantom fields (don't exist in modeli_osnova table)
DELETE FROM field_definitions
  WHERE entity_type = 'modeli_osnova'
    AND field_name IN ('importer_id', 'sezon', 'pol', 'razmer_min', 'razmer_max', 'brand', 'predmet', 'strana_proiz', 'zametki');

-- 3. Insert missing fields (exist in DB/schema but not in field_definitions)
INSERT INTO field_definitions (entity_type, field_name, display_name, field_type, section, sort_order, is_system, is_visible)
VALUES
  ('modeli_osnova', 'material',            'Материал',            'text',   'Основные',   60,  false, true),
  ('modeli_osnova', 'composition',         'Состав (англ)',       'text',   'Основные',   65,  false, true),
  ('modeli_osnova', 'tip_kollekcii',       'Тип коллекции',      'text',   'Основные',   70,  false, true),
  ('modeli_osnova', 'sku_china',           'SKU Китай',           'text',   'Основные',   75,  false, true),
  ('modeli_osnova', 'upakovka',            'Упаковка',            'text',   'Основные',   80,  false, true),
  ('modeli_osnova', 'kratnost_koroba',     'Кратность короба',    'number', 'Логистика',  130, false, true),
  ('modeli_osnova', 'srok_proizvodstva',   'Срок производства',   'text',   'Логистика',  135, false, true),
  ('modeli_osnova', 'komplektaciya',       'Комплектация',        'text',   'Логистика',  140, false, true),
  ('modeli_osnova', 'gruppa_sertifikata',  'Группа сертификата',  'text',   'Логистика',  145, false, true),
  ('modeli_osnova', 'nazvanie_etiketka',   'Название этикетка',   'text',   'Контент',    155, false, true),
  ('modeli_osnova', 'tegi',                'Теги',                'text',   'Контент',    170, false, true),
  ('modeli_osnova', 'notion_link',         'Notion ссылка',       'url',    'Контент',    175, false, true)
ON CONFLICT DO NOTHING;

COMMIT;
