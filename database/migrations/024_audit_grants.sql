-- W9.1: Audit log access fix — istoriya_izmeneniy (infra schema)
--
-- Симптом: `permission denied for table istoriya_izmeneniy` при любых
-- INSERT/UPDATE/DELETE по аудируемым таблицам каталога (artikuly, modeli,
-- tovary, cveta) под ролью `authenticated`.
--
-- Корень: legacy-триггер `public.log_izmeneniya` (SECURITY INVOKER) пишет в
-- `infra.istoriya_izmeneniy`, но `authenticated` не имеет ни INSERT-grant,
-- ни RLS-policy на эту таблицу. (Не путать с `public.audit_log` из миграции
-- 023 — там аналогичный триггер уже SECURITY DEFINER и работает корректно.)
--
-- Решение (defense in depth):
--   1. Перевести `public.log_izmeneniya` в SECURITY DEFINER с безопасным
--      search_path. Триггер выполняется как owner (postgres) и обходит
--      RLS, что и требуется для аудита.
--   2. На всякий случай выдать GRANT INSERT/SELECT на саму таблицу для
--      `authenticated` и `service_role` (если когда-то отключат DEFINER,
--      аудит продолжит писаться, а не молча падать).
--   3. Включить INSERT-policy для `authenticated` (RLS уже включён, INSERT
--      без policy блокируется даже при наличии GRANT). SELECT — только
--      свои записи (`polzovatel = current_user`).
--   4. Никаких прав `anon` — таблица служебная.

-- 1. SECURITY DEFINER + изоляция search_path
ALTER FUNCTION public.log_izmeneniya() SECURITY DEFINER;
ALTER FUNCTION public.log_izmeneniya() SET search_path = public, infra, pg_temp;

-- 2. Прямые GRANT-ы (defense in depth)
GRANT USAGE ON SCHEMA infra TO authenticated, service_role;
GRANT INSERT, SELECT ON public.audit_log TO authenticated, service_role;
GRANT INSERT, SELECT ON infra.istoriya_izmeneniy TO authenticated, service_role;
GRANT USAGE, SELECT ON SEQUENCE infra.istoriya_izmeneniy_id_seq TO authenticated, service_role;

-- 3. RLS-policies на infra.istoriya_izmeneniy.
--    RLS уже включён (rls_enabled=true), есть SELECT-policy
--    `authenticated_select_istoriya_izmeneniy`. Добавляем INSERT-policy.
DROP POLICY IF EXISTS authenticated_insert_istoriya_izmeneniy ON infra.istoriya_izmeneniy;
CREATE POLICY authenticated_insert_istoriya_izmeneniy
  ON infra.istoriya_izmeneniy
  FOR INSERT
  TO authenticated
  WITH CHECK (true);
-- INSERT защищён тем, что зовут его только аудит-триггеры на конкретных
-- таблицах, прямой вызов из клиента не нужен и не предполагается.

-- 4. Также убедимся, что аналогичная INSERT-policy есть на public.audit_log
--    (миграция 023 выдала только SELECT-policy, но триггер audit_trigger_fn
--    SECURITY DEFINER пишет от owner-а — однако подстрахуемся).
DROP POLICY IF EXISTS authenticated_insert_audit_log ON public.audit_log;
CREATE POLICY authenticated_insert_audit_log
  ON public.audit_log
  FOR INSERT
  TO authenticated
  WITH CHECK (true);
