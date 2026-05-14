-- W10.42: Миграция cveta.status_id с product-статусов на color-статусы
--
-- Контекст:
--   До этой миграции cveta.status_id указывал на public.statusy с tip='product'
--   (id=8,9,10,11,12,14), что приводило к тому, что фильтр статусов на
--   /catalog/colors (фильтрующий по tip='color') возвращал 0/146 — все цвета
--   были невидимы для фильтра.
--
--   Color-статусы (statusy.tip='color') — это упрощённый набор из 3 значений:
--     34 = "Продается"
--     35 = "Выводим"
--     36 = "Архив"
--   У color нет фаз жизненного цикла (Подготовка/План/Запуск/В продаже) как у
--   product/model — у color есть только три состояния. Поэтому маппинг
--   "активных" фаз product (Подготовка/План/Запуск/Продается) выполняется
--   в color "Продается".
--
-- Маппинг product (src) → color (dst):
--    8  Продается  → 34 Продается
--    9  Выводим    → 35 Выводим
--   10  Архив      → 36 Архив
--   11  Подготовка → 34 Продается  (semantic fallback: цвет активный/в работе)
--   12  План       → 34 Продается  (semantic fallback)
--   14  Запуск     → 34 Продается  (semantic fallback)
--
-- Текущее распределение (на момент создания миграции):
--   status_id=8  (Продается, product)  → 52 цвета  → станут 34
--   status_id=9  (Выводим, product)    → 19 цветов → станут 35
--   status_id=11 (Подготовка, product) → 10 цветов → станут 34
--   status_id=12 (План, product)       → 30 цветов → станут 34
--   status_id=14 (Запуск, product)     → 23 цвета  → станут 34
--   status_id=NULL                     → 12 цветов → остаются NULL
--
-- После миграции:
--   34 (Продается, color) → 115 цветов
--   35 (Выводим, color)   → 19 цветов
--   36 (Архив, color)     → 0 цветов
--   NULL                  → 12 цветов
--
-- Триггер запрещает впредь писать в cveta.status_id ничего кроме color-статусов.

BEGIN;

-- 1. Перенос данных: product → color
-- Маппинг по nazvanie там, где значение совпадает; orphan-фазы маппим в "Продается".
UPDATE public.cveta
   SET status_id = 34
 WHERE status_id IN (8, 11, 12, 14);

UPDATE public.cveta
   SET status_id = 35
 WHERE status_id = 9;

UPDATE public.cveta
   SET status_id = 36
 WHERE status_id = 10;

-- 2. Защитный триггер: cveta.status_id может ссылаться только на color-статусы.
CREATE OR REPLACE FUNCTION public.check_cveta_status_tip()
RETURNS trigger AS $$
DECLARE
  v_tip text;
BEGIN
  IF NEW.status_id IS NOT NULL THEN
    SELECT tip INTO v_tip FROM public.statusy WHERE id = NEW.status_id;
    IF v_tip IS NULL THEN
      RAISE EXCEPTION 'cveta.status_id=% does not exist in public.statusy', NEW.status_id;
    END IF;
    IF v_tip <> 'color' THEN
      RAISE EXCEPTION 'cveta.status_id must reference statusy.tip = ''color'' (got status_id=%, tip=%)', NEW.status_id, v_tip;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS check_cveta_status_tip_trg ON public.cveta;

CREATE TRIGGER check_cveta_status_tip_trg
  BEFORE INSERT OR UPDATE OF status_id ON public.cveta
  FOR EACH ROW EXECUTE FUNCTION public.check_cveta_status_tip();

-- 3. Sanity-check: после миграции не должно остаться cveta со status_id, ссылающимся на не-color.
DO $$
DECLARE
  v_bad int;
BEGIN
  SELECT COUNT(*) INTO v_bad
    FROM public.cveta c
    JOIN public.statusy s ON s.id = c.status_id
   WHERE s.tip <> 'color';
  IF v_bad > 0 THEN
    RAISE EXCEPTION 'Migration 026 failed sanity check: % cveta rows still reference non-color statusy', v_bad;
  END IF;
END;
$$;

COMMIT;
