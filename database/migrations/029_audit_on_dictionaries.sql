-- W10.40: Audit_trigger_fn на справочных таблицах
-- Контекст: после W7.1 аудит работает только на основных каталожных
-- таблицах (modeli/artikuly/tovary/cveta/brendy/kollekcii/kategorii/
-- modeli_osnova/sertifikaty). При редактировании справочников
-- (атрибуты, фабрики, типы коллекций, размеры, склейки) аудит не
-- писался — для UI карточки склейки (W10.25) и кнопки "Откатить"
-- (W10.13) это слепое пятно.
--
-- Шаги:
--   1. На skleyki_wb / skleyki_ozon снять legacy log_izmeneniya
--      (его уже не убрала миграция 028 — она работала только по
--      каталожному списку из 9 таблиц).
--   2. Поставить audit_trigger_fn на: atributy, fabriki, tipy_kollekciy,
--      kategoriya_atributy, modeli_osnova_razmery, skleyki_wb, skleyki_ozon.
--   3. cvet_kategoriya — пропускаем (composite PK без id, audit_trigger_fn
--      требует поле id).
--
-- W10.41: на tipy_kollekciy была одна "ALL" RLS-политика для authenticated
-- (qual=true, with_check=true). Делим на отдельные SELECT/INSERT/UPDATE/
-- DELETE — это лучше читаемо и легче точечно ограничивать в будущем.

-- ── 1. Снять legacy-аудит со склеек ─────────────────────────────────
DROP TRIGGER IF EXISTS tr_skleyki_wb_izmeneniya   ON public.skleyki_wb;
DROP TRIGGER IF EXISTS tr_skleyki_ozon_izmeneniya ON public.skleyki_ozon;

-- ── 2. Audit на справочниках ────────────────────────────────────────
DO $$
DECLARE
  t TEXT;
  tables TEXT[] := ARRAY[
    'atributy','fabriki','tipy_kollekciy',
    'kategoriya_atributy','modeli_osnova_razmery',
    'skleyki_wb','skleyki_ozon'
  ];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema='public' AND table_name=t
    ) THEN
      EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I',
        'audit_' || t, t);
      EXECUTE format(
        'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON public.%I '
        'FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_fn()',
        'audit_' || t, t);
    END IF;
  END LOOP;
END$$;

-- ── 3. W10.41: разделить ALL-политику на tipy_kollekciy ─────────────
DROP POLICY IF EXISTS "authenticated write" ON public.tipy_kollekciy;
-- "authenticated read" оставляем как есть (SELECT, qual=true).

CREATE POLICY tipy_kollekciy_insert ON public.tipy_kollekciy
  FOR INSERT TO authenticated WITH CHECK (true);

CREATE POLICY tipy_kollekciy_update ON public.tipy_kollekciy
  FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY tipy_kollekciy_delete ON public.tipy_kollekciy
  FOR DELETE TO authenticated USING (true);
