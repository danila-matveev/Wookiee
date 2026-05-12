-- W7.1: Audit log — fix-points of all catalog mutations
CREATE TABLE IF NOT EXISTS public.audit_log (
  id           BIGSERIAL PRIMARY KEY,
  table_name   TEXT NOT NULL,
  row_id       TEXT NOT NULL,            -- TEXT, не INT — позволяет работать с разными PK
  user_id      UUID,                     -- auth.uid() из jwt; может быть NULL для service_role
  action       TEXT NOT NULL CHECK (action IN ('INSERT','UPDATE','DELETE')),
  before       JSONB,                    -- NULL для INSERT
  after        JSONB,                    -- NULL для DELETE
  changed      JSONB,                    -- diff (только изменённые ключи); NULL для INSERT/DELETE
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_log_table_row_idx
  ON public.audit_log(table_name, row_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_user_idx
  ON public.audit_log(user_id, created_at DESC);

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS audit_log_select ON public.audit_log;
CREATE POLICY audit_log_select ON public.audit_log
  FOR SELECT TO authenticated USING (true);
GRANT SELECT ON public.audit_log TO authenticated;

-- Триггер-функция: пишет before/after/changed
CREATE OR REPLACE FUNCTION public.audit_trigger_fn()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user UUID;
  v_before JSONB;
  v_after  JSONB;
  v_changed JSONB := '{}'::jsonb;
  k TEXT;
BEGIN
  BEGIN
    v_user := auth.uid();
  EXCEPTION WHEN OTHERS THEN v_user := NULL;
  END;

  IF TG_OP = 'INSERT' THEN
    v_after := to_jsonb(NEW);
    INSERT INTO public.audit_log(table_name, row_id, user_id, action, before, after, changed)
    VALUES (TG_TABLE_NAME, (v_after->>'id')::text, v_user, 'INSERT', NULL, v_after, NULL);
    RETURN NEW;
  ELSIF TG_OP = 'UPDATE' THEN
    v_before := to_jsonb(OLD);
    v_after  := to_jsonb(NEW);
    FOR k IN SELECT jsonb_object_keys(v_after) LOOP
      IF v_after->k IS DISTINCT FROM v_before->k THEN
        v_changed := v_changed || jsonb_build_object(k,
          jsonb_build_object('from', v_before->k, 'to', v_after->k));
      END IF;
    END LOOP;
    IF v_changed <> '{}'::jsonb THEN
      INSERT INTO public.audit_log(table_name, row_id, user_id, action, before, after, changed)
      VALUES (TG_TABLE_NAME, (v_after->>'id')::text, v_user, 'UPDATE', v_before, v_after, v_changed);
    END IF;
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    v_before := to_jsonb(OLD);
    INSERT INTO public.audit_log(table_name, row_id, user_id, action, before, after, changed)
    VALUES (TG_TABLE_NAME, (v_before->>'id')::text, v_user, 'DELETE', v_before, NULL, NULL);
    RETURN OLD;
  END IF;
  RETURN NULL;
END;
$$;

-- Триггеры на 9 таблиц (по плану). Если какой-то таблицы нет — пропускаем через DO block.
DO $$
DECLARE
  t TEXT;
  tables TEXT[] := ARRAY[
    'modeli_osnova','modeli','artikuly','tovary',
    'cveta','brendy','kollekcii','kategorii','sertifikaty'
  ];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=t) THEN
      EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I', 'audit_'||t, t);
      EXECUTE format(
        'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON public.%I '
        'FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_fn()',
        'audit_'||t, t);
    END IF;
  END LOOP;
END$$;
