-- ============================================
-- Триггеры для версионирования изменений
-- База данных спецификаций товаров Wookiee
-- ============================================

-- ============================================
-- ФУНКЦИЯ ЛОГИРОВАНИЯ ИЗМЕНЕНИЙ
-- ============================================

CREATE OR REPLACE FUNCTION log_izmeneniya()
RETURNS TRIGGER AS $$
DECLARE
    v_old_data JSONB;
    v_new_data JSONB;
    v_key TEXT;
    v_old_value TEXT;
    v_new_value TEXT;
    v_zapis_id INT;
BEGIN
    -- Определяем ID записи
    IF TG_OP = 'DELETE' THEN
        v_zapis_id := OLD.id;
    ELSE
        v_zapis_id := NEW.id;
    END IF;

    -- INSERT: записываем факт создания
    IF TG_OP = 'INSERT' THEN
        INSERT INTO istoriya_izmeneniy (tablica, zapis_id, pole, staroe_znachenie, novoe_znachenie, tip_operacii, polzovatel)
        VALUES (TG_TABLE_NAME, v_zapis_id, NULL, NULL, row_to_json(NEW)::TEXT, 'INSERT', current_user);
        RETURN NEW;
    END IF;

    -- DELETE: записываем факт удаления
    IF TG_OP = 'DELETE' THEN
        INSERT INTO istoriya_izmeneniy (tablica, zapis_id, pole, staroe_znachenie, novoe_znachenie, tip_operacii, polzovatel)
        VALUES (TG_TABLE_NAME, v_zapis_id, NULL, row_to_json(OLD)::TEXT, NULL, 'DELETE', current_user);
        RETURN OLD;
    END IF;

    -- UPDATE: записываем изменения по полям
    IF TG_OP = 'UPDATE' THEN
        v_old_data := row_to_json(OLD)::JSONB;
        v_new_data := row_to_json(NEW)::JSONB;

        -- Проходим по всем ключам и сравниваем значения
        FOR v_key IN SELECT jsonb_object_keys(v_new_data)
        LOOP
            -- Пропускаем служебные поля
            IF v_key IN ('id', 'created_at', 'updated_at') THEN
                CONTINUE;
            END IF;

            v_old_value := v_old_data ->> v_key;
            v_new_value := v_new_data ->> v_key;

            -- Если значения отличаются - записываем изменение
            IF v_old_value IS DISTINCT FROM v_new_value THEN
                INSERT INTO istoriya_izmeneniy (tablica, zapis_id, pole, staroe_znachenie, novoe_znachenie, tip_operacii, polzovatel)
                VALUES (TG_TABLE_NAME, v_zapis_id, v_key, v_old_value, v_new_value, 'UPDATE', current_user);
            END IF;
        END LOOP;

        RETURN NEW;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION log_izmeneniya() IS 'Функция логирования изменений для версионирования';

-- ============================================
-- ФУНКЦИЯ ОБНОВЛЕНИЯ updated_at
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_updated_at() IS 'Функция автоматического обновления поля updated_at';

-- ============================================
-- ТРИГГЕРЫ ДЛЯ ТАБЛИЦЫ MODELI
-- ============================================

-- Триггер версионирования
DROP TRIGGER IF EXISTS tr_modeli_izmeneniya ON modeli;
CREATE TRIGGER tr_modeli_izmeneniya
    AFTER INSERT OR UPDATE OR DELETE ON modeli
    FOR EACH ROW
    EXECUTE FUNCTION log_izmeneniya();

-- Триггер обновления updated_at
DROP TRIGGER IF EXISTS tr_modeli_updated_at ON modeli;
CREATE TRIGGER tr_modeli_updated_at
    BEFORE UPDATE ON modeli
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================
-- ТРИГГЕРЫ ДЛЯ ТАБЛИЦЫ ARTIKULY
-- ============================================

-- Триггер версионирования
DROP TRIGGER IF EXISTS tr_artikuly_izmeneniya ON artikuly;
CREATE TRIGGER tr_artikuly_izmeneniya
    AFTER INSERT OR UPDATE OR DELETE ON artikuly
    FOR EACH ROW
    EXECUTE FUNCTION log_izmeneniya();

-- Триггер обновления updated_at
DROP TRIGGER IF EXISTS tr_artikuly_updated_at ON artikuly;
CREATE TRIGGER tr_artikuly_updated_at
    BEFORE UPDATE ON artikuly
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================
-- ТРИГГЕРЫ ДЛЯ ТАБЛИЦЫ TOVARY
-- ============================================

-- Триггер версионирования
DROP TRIGGER IF EXISTS tr_tovary_izmeneniya ON tovary;
CREATE TRIGGER tr_tovary_izmeneniya
    AFTER INSERT OR UPDATE OR DELETE ON tovary
    FOR EACH ROW
    EXECUTE FUNCTION log_izmeneniya();

-- Триггер обновления updated_at
DROP TRIGGER IF EXISTS tr_tovary_updated_at ON tovary;
CREATE TRIGGER tr_tovary_updated_at
    BEFORE UPDATE ON tovary
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================
-- ТРИГГЕРЫ ДЛЯ ТАБЛИЦЫ CVETA
-- ============================================

-- Триггер версионирования
DROP TRIGGER IF EXISTS tr_cveta_izmeneniya ON cveta;
CREATE TRIGGER tr_cveta_izmeneniya
    AFTER INSERT OR UPDATE OR DELETE ON cveta
    FOR EACH ROW
    EXECUTE FUNCTION log_izmeneniya();

-- Триггер обновления updated_at
DROP TRIGGER IF EXISTS tr_cveta_updated_at ON cveta;
CREATE TRIGGER tr_cveta_updated_at
    BEFORE UPDATE ON cveta
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================
-- ТРИГГЕРЫ ДЛЯ ТАБЛИЦЫ SKLEYKI_WB
-- ============================================

-- Триггер версионирования
DROP TRIGGER IF EXISTS tr_skleyki_wb_izmeneniya ON skleyki_wb;
CREATE TRIGGER tr_skleyki_wb_izmeneniya
    AFTER INSERT OR UPDATE OR DELETE ON skleyki_wb
    FOR EACH ROW
    EXECUTE FUNCTION log_izmeneniya();

-- Триггер обновления updated_at
DROP TRIGGER IF EXISTS tr_skleyki_wb_updated_at ON skleyki_wb;
CREATE TRIGGER tr_skleyki_wb_updated_at
    BEFORE UPDATE ON skleyki_wb
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================
-- ТРИГГЕРЫ ДЛЯ ТАБЛИЦЫ SKLEYKI_OZON
-- ============================================

-- Триггер версионирования
DROP TRIGGER IF EXISTS tr_skleyki_ozon_izmeneniya ON skleyki_ozon;
CREATE TRIGGER tr_skleyki_ozon_izmeneniya
    AFTER INSERT OR UPDATE OR DELETE ON skleyki_ozon
    FOR EACH ROW
    EXECUTE FUNCTION log_izmeneniya();

-- Триггер обновления updated_at
DROP TRIGGER IF EXISTS tr_skleyki_ozon_updated_at ON skleyki_ozon;
CREATE TRIGGER tr_skleyki_ozon_updated_at
    BEFORE UPDATE ON skleyki_ozon
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================
-- ПОЛЕЗНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С ИСТОРИЕЙ
-- ============================================

-- Получить историю изменений записи
CREATE OR REPLACE FUNCTION get_istoriya_zapisi(
    p_tablica VARCHAR(50),
    p_zapis_id INT
)
RETURNS TABLE (
    pole VARCHAR(100),
    staroe_znachenie TEXT,
    novoe_znachenie TEXT,
    tip_operacii VARCHAR(20),
    polzovatel VARCHAR(100),
    data_izmeneniya TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        i.pole,
        i.staroe_znachenie,
        i.novoe_znachenie,
        i.tip_operacii,
        i.polzovatel,
        i.data_izmeneniya
    FROM istoriya_izmeneniy i
    WHERE i.tablica = p_tablica AND i.zapis_id = p_zapis_id
    ORDER BY i.data_izmeneniya DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_istoriya_zapisi(VARCHAR, INT) IS 'Получить историю изменений для конкретной записи';

-- Получить все изменения за период
CREATE OR REPLACE FUNCTION get_izmeneniya_za_period(
    p_data_ot TIMESTAMP,
    p_data_do TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
RETURNS TABLE (
    tablica VARCHAR(50),
    zapis_id INT,
    pole VARCHAR(100),
    staroe_znachenie TEXT,
    novoe_znachenie TEXT,
    tip_operacii VARCHAR(20),
    polzovatel VARCHAR(100),
    data_izmeneniya TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        i.tablica,
        i.zapis_id,
        i.pole,
        i.staroe_znachenie,
        i.novoe_znachenie,
        i.tip_operacii,
        i.polzovatel,
        i.data_izmeneniya
    FROM istoriya_izmeneniy i
    WHERE i.data_izmeneniya BETWEEN p_data_ot AND p_data_do
    ORDER BY i.data_izmeneniya DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_izmeneniya_za_period(TIMESTAMP, TIMESTAMP) IS 'Получить все изменения за указанный период';

-- ============================================
-- ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ
-- ============================================

/*
-- Посмотреть историю изменений модели с id=1
SELECT * FROM get_istoriya_zapisi('modeli', 1);

-- Посмотреть все изменения за последние 7 дней
SELECT * FROM get_izmeneniya_za_period(CURRENT_TIMESTAMP - INTERVAL '7 days');

-- Посмотреть все INSERT операции
SELECT * FROM istoriya_izmeneniy WHERE tip_operacii = 'INSERT' ORDER BY data_izmeneniya DESC;

-- Посмотреть кто что менял
SELECT
    polzovatel,
    tablica,
    COUNT(*) as kolichestvo_izmeneniy
FROM istoriya_izmeneniy
GROUP BY polzovatel, tablica
ORDER BY kolichestvo_izmeneniy DESC;
*/
