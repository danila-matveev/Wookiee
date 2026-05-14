-- W10.39: Удалить legacy-аудит через log_izmeneniya() на каталожных таблицах
-- Контекст: после W7.1 (migration 023) на каталожных таблицах висят ДВА
-- audit-триггера на одно изменение:
--   * audit_<table>           → public.audit_log         (новый, W7.1)
--   * tr_<table>_izmeneniya   → infra.istoriya_izmeneniy (legacy)
-- Каждое UPDATE пишется в обе таблицы → double-write, дрейф объёмов,
-- путаница для UI (W10.12, W10.25 читают только public.audit_log).
--
-- Сохраняем:
--   * функцию public.log_izmeneniya() — может ещё писать internal trigger
--     из других схем;
--   * infra.istoriya_izmeneniy — исторические данные не трогаем.
-- Удаляем ТОЛЬКО триггеры на каталожных таблицах.
--
-- По факту в БД (проверено через information_schema.triggers) legacy
-- триггеры висят на 4 таблицах: artikuly, cveta, modeli, tovary.
-- Остальные 5 (brendy, kategorii, kollekcii, modeli_osnova, sertifikaty)
-- легаси-триггеры уже не имеют — DROP IF EXISTS-сейф.

DO $$
DECLARE
  t TEXT;
  tables TEXT[] := ARRAY[
    'artikuly','cveta','modeli','tovary',
    'modeli_osnova','brendy','kollekcii','kategorii','sertifikaty'
  ];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I',
      'tr_' || t || '_izmeneniya', t);
  END LOOP;
END$$;
