-- ============================================
-- База данных спецификаций товаров Wookiee
-- PostgreSQL DDL Schema
-- ВЕРСИЯ 2.0 - Модель основа как верхний уровень
-- ============================================

-- Удаление таблиц (в правильном порядке для FK)
DROP TABLE IF EXISTS tovary_skleyki_ozon CASCADE;
DROP TABLE IF EXISTS tovary_skleyki_wb CASCADE;
DROP TABLE IF EXISTS istoriya_izmeneniy CASCADE;
DROP TABLE IF EXISTS tovary CASCADE;
DROP TABLE IF EXISTS artikuly CASCADE;
DROP TABLE IF EXISTS skleyki_ozon CASCADE;
DROP TABLE IF EXISTS skleyki_wb CASCADE;
DROP TABLE IF EXISTS modeli CASCADE;
DROP TABLE IF EXISTS modeli_osnova CASCADE;
DROP TABLE IF EXISTS cveta CASCADE;
DROP TABLE IF EXISTS fabriki CASCADE;
DROP TABLE IF EXISTS importery CASCADE;
DROP TABLE IF EXISTS razmery CASCADE;
DROP TABLE IF EXISTS statusy CASCADE;
DROP TABLE IF EXISTS kollekcii CASCADE;
DROP TABLE IF EXISTS kategorii CASCADE;

-- ============================================
-- 1. СПРАВОЧНИКИ
-- ============================================

-- Категории товаров
CREATE TABLE kategorii (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(100) NOT NULL UNIQUE
);
COMMENT ON TABLE kategorii IS 'Категории товаров (Комплект белья, Трусы, Боди)';
COMMENT ON COLUMN kategorii.id IS 'Идентификатор категории';
COMMENT ON COLUMN kategorii.nazvanie IS 'Название категории';

-- Коллекции
CREATE TABLE kollekcii (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(100) NOT NULL UNIQUE
);
COMMENT ON TABLE kollekcii IS 'Коллекции (Трикотажное белье, Наборы трусов и т.д.)';
COMMENT ON COLUMN kollekcii.id IS 'Идентификатор коллекции';
COMMENT ON COLUMN kollekcii.nazvanie IS 'Название коллекции';

-- Статусы (единые для моделей, артикулов, цветов, товаров)
CREATE TABLE statusy (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(50) NOT NULL UNIQUE
);
COMMENT ON TABLE statusy IS 'Единые статусы (Продается, Выводим, Архив, Подготовка, План, Новый, Запуск)';
COMMENT ON COLUMN statusy.id IS 'Идентификатор статуса';
COMMENT ON COLUMN statusy.nazvanie IS 'Название статуса';

-- Размеры
CREATE TABLE razmery (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(10) NOT NULL UNIQUE,
    poryadok INT NOT NULL DEFAULT 0
);
COMMENT ON TABLE razmery IS 'Справочник размеров одежды';
COMMENT ON COLUMN razmery.id IS 'Идентификатор размера';
COMMENT ON COLUMN razmery.nazvanie IS 'Размер (XS, S, M, L, XL, XXL)';
COMMENT ON COLUMN razmery.poryadok IS 'Порядок сортировки';

-- Импортеры
CREATE TABLE importery (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(100) NOT NULL UNIQUE,
    nazvanie_en VARCHAR(100),
    inn VARCHAR(20),
    adres TEXT
);
COMMENT ON TABLE importery IS 'Импортеры (юридические лица)';
COMMENT ON COLUMN importery.id IS 'Идентификатор импортера';
COMMENT ON COLUMN importery.nazvanie IS 'Название (ИП Медведева П.В., ООО Вуки)';
COMMENT ON COLUMN importery.nazvanie_en IS 'Название на английском (Importer)';
COMMENT ON COLUMN importery.inn IS 'ИНН';
COMMENT ON COLUMN importery.adres IS 'Адрес импортера';

-- Фабрики
CREATE TABLE fabriki (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(100) NOT NULL UNIQUE,
    strana VARCHAR(50)
);
COMMENT ON TABLE fabriki IS 'Фабрики-производители';
COMMENT ON COLUMN fabriki.id IS 'Идентификатор фабрики';
COMMENT ON COLUMN fabriki.nazvanie IS 'Название фабрики';
COMMENT ON COLUMN fabriki.strana IS 'Страна производства';

-- ============================================
-- 2. ЦВЕТА
-- ============================================

CREATE TABLE cveta (
    id SERIAL PRIMARY KEY,
    color_code VARCHAR(20) NOT NULL UNIQUE,
    cvet VARCHAR(200),
    color VARCHAR(200),
    lastovica VARCHAR(50),
    status_id INT REFERENCES statusy(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE cveta IS 'Справочник цветов (из Аналитики цветов)';
COMMENT ON COLUMN cveta.id IS 'Идентификатор цвета';
COMMENT ON COLUMN cveta.color_code IS 'Код цвета (2, w3, 36...)';
COMMENT ON COLUMN cveta.cvet IS 'Цвет на русском';
COMMENT ON COLUMN cveta.color IS 'Color на английском';
COMMENT ON COLUMN cveta.lastovica IS 'Цвет ластовицы (Gusset)';
COMMENT ON COLUMN cveta.status_id IS 'Статус цвета';
COMMENT ON COLUMN cveta.created_at IS 'Дата создания записи';
COMMENT ON COLUMN cveta.updated_at IS 'Дата последнего обновления';

-- ============================================
-- 3. МОДЕЛИ ОСНОВА (ВЕРХНИЙ УРОВЕНЬ)
-- Хранит ВСЕ общие характеристики товара
-- ============================================

CREATE TABLE modeli_osnova (
    id SERIAL PRIMARY KEY,
    kod VARCHAR(50) NOT NULL UNIQUE,

    -- Классификация
    kategoriya_id INT REFERENCES kategorii(id),
    kollekciya_id INT REFERENCES kollekcii(id),
    fabrika_id INT REFERENCES fabriki(id),

    -- Размеры и упаковка
    razmery_modeli VARCHAR(50),
    sku_china VARCHAR(100),
    upakovka VARCHAR(100),
    ves_kg DECIMAL(5,3),
    dlina_cm DECIMAL(5,1),
    shirina_cm DECIMAL(5,1),
    vysota_cm DECIMAL(5,1),
    kratnost_koroba INT,
    srok_proizvodstva VARCHAR(50),
    komplektaciya TEXT,

    -- Материал и состав
    material VARCHAR(200),
    sostav_syrya TEXT,
    composition TEXT,

    -- Характеристики товара
    dlya_kakoy_grudi VARCHAR(200),
    stepen_podderzhki VARCHAR(200),
    forma_chashki VARCHAR(200),
    regulirovka VARCHAR(200),
    zastezhka VARCHAR(200),
    posadka_trusov VARCHAR(200),
    vid_trusov VARCHAR(200),
    naznachenie VARCHAR(200),
    stil VARCHAR(200),
    po_nastroeniyu VARCHAR(200),

    -- Логистика и сертификация
    tnved VARCHAR(20),
    gruppa_sertifikata VARCHAR(50),

    -- Контент (общий для всех вариаций)
    nazvanie_etiketka VARCHAR(200),
    nazvanie_sayt VARCHAR(200),
    opisanie_sayt TEXT,
    details TEXT,
    description TEXT,
    tegi TEXT,
    notion_link VARCHAR(500),

    -- Служебные поля
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE modeli_osnova IS 'Базовые модели (Vuki, Moon, Ruby...) - ВЕРХНИЙ УРОВЕНЬ с характеристиками товара';
COMMENT ON COLUMN modeli_osnova.id IS 'Идентификатор базовой модели';
COMMENT ON COLUMN modeli_osnova.kod IS 'Код модели основы (Vuki, Moon, Ruby, Set Vuki...)';
COMMENT ON COLUMN modeli_osnova.kategoriya_id IS 'Категория (FK)';
COMMENT ON COLUMN modeli_osnova.kollekciya_id IS 'Коллекция (FK)';
COMMENT ON COLUMN modeli_osnova.fabrika_id IS 'Фабрика (FK)';
COMMENT ON COLUMN modeli_osnova.razmery_modeli IS 'Размеры модели (S, M, L, XL)';
COMMENT ON COLUMN modeli_osnova.sku_china IS 'SKU CHINA';
COMMENT ON COLUMN modeli_osnova.upakovka IS 'Упаковка';
COMMENT ON COLUMN modeli_osnova.ves_kg IS 'Вес (кг)';
COMMENT ON COLUMN modeli_osnova.dlina_cm IS 'Длина (см)';
COMMENT ON COLUMN modeli_osnova.shirina_cm IS 'Ширина (см)';
COMMENT ON COLUMN modeli_osnova.vysota_cm IS 'Высота (см)';
COMMENT ON COLUMN modeli_osnova.kratnost_koroba IS 'Кратность короба';
COMMENT ON COLUMN modeli_osnova.srok_proizvodstva IS 'Срок производства';
COMMENT ON COLUMN modeli_osnova.komplektaciya IS 'Комплектация';
COMMENT ON COLUMN modeli_osnova.material IS 'Материал';
COMMENT ON COLUMN modeli_osnova.sostav_syrya IS 'Состав сырья';
COMMENT ON COLUMN modeli_osnova.composition IS 'Composition (английский)';
COMMENT ON COLUMN modeli_osnova.dlya_kakoy_grudi IS 'Для какой груди';
COMMENT ON COLUMN modeli_osnova.stepen_podderzhki IS 'Степень поддержки груди';
COMMENT ON COLUMN modeli_osnova.forma_chashki IS 'Форма чашки';
COMMENT ON COLUMN modeli_osnova.regulirovka IS 'Регулировка';
COMMENT ON COLUMN modeli_osnova.zastezhka IS 'Застежка';
COMMENT ON COLUMN modeli_osnova.posadka_trusov IS 'Посадка трусов';
COMMENT ON COLUMN modeli_osnova.vid_trusov IS 'Вид трусов';
COMMENT ON COLUMN modeli_osnova.naznachenie IS 'Назначение';
COMMENT ON COLUMN modeli_osnova.stil IS 'Стиль';
COMMENT ON COLUMN modeli_osnova.po_nastroeniyu IS 'По настроению';
COMMENT ON COLUMN modeli_osnova.tnved IS 'ТНВЭД';
COMMENT ON COLUMN modeli_osnova.gruppa_sertifikata IS 'Группа сертификата';
COMMENT ON COLUMN modeli_osnova.nazvanie_etiketka IS 'Название для этикетки';
COMMENT ON COLUMN modeli_osnova.nazvanie_sayt IS 'Название для сайта';
COMMENT ON COLUMN modeli_osnova.opisanie_sayt IS 'Описание для сайта';
COMMENT ON COLUMN modeli_osnova.details IS 'Details (детали на английском)';
COMMENT ON COLUMN modeli_osnova.description IS 'Description (описание на английском)';
COMMENT ON COLUMN modeli_osnova.tegi IS 'Теги';
COMMENT ON COLUMN modeli_osnova.notion_link IS 'Ссылка на Notion';
COMMENT ON COLUMN modeli_osnova.created_at IS 'Дата создания записи';
COMMENT ON COLUMN modeli_osnova.updated_at IS 'Дата последнего обновления';

-- Индексы для модели основы
CREATE INDEX idx_modeli_osnova_kategoriya ON modeli_osnova(kategoriya_id);
CREATE INDEX idx_modeli_osnova_kollekciya ON modeli_osnova(kollekciya_id);

-- ============================================
-- 4. МОДЕЛИ (ВАРИАЦИИ НА РАЗНЫХ ЮРЛИЦАХ)
-- Хранит только специфику импортера/юрлица
-- ============================================

CREATE TABLE modeli (
    id SERIAL PRIMARY KEY,

    -- Код и название вариации
    kod VARCHAR(50) NOT NULL UNIQUE,
    nazvanie VARCHAR(100) NOT NULL,
    nazvanie_en VARCHAR(100),
    artikul_modeli VARCHAR(100),

    -- Связь с основой
    model_osnova_id INT REFERENCES modeli_osnova(id),

    -- Специфика юрлица
    importer_id INT REFERENCES importery(id),
    status_id INT REFERENCES statusy(id),
    nabor BOOLEAN DEFAULT FALSE,
    rossiyskiy_razmer VARCHAR(50),

    -- Служебные поля
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE modeli IS 'Модели товаров - вариации на разных юрлицах (Vuki-ИП, Vuki2-ООО)';
COMMENT ON COLUMN modeli.id IS 'Идентификатор модели';
COMMENT ON COLUMN modeli.kod IS 'Код вариации (Vuki, VukiN, Vuki2, VukiN2...)';
COMMENT ON COLUMN modeli.nazvanie IS 'Название модели (Vuki, Vuki animal, Vuki выстиранки...)';
COMMENT ON COLUMN modeli.nazvanie_en IS 'Name (английское название)';
COMMENT ON COLUMN modeli.artikul_modeli IS 'Артикул модели (уникален для каждого юрлица)';
COMMENT ON COLUMN modeli.model_osnova_id IS 'Модель основа (FK) - связь с характеристиками';
COMMENT ON COLUMN modeli.importer_id IS 'Импортер/юрлицо (ИП или ООО)';
COMMENT ON COLUMN modeli.status_id IS 'Статус модели';
COMMENT ON COLUMN modeli.nabor IS 'Набор (да/нет)';
COMMENT ON COLUMN modeli.rossiyskiy_razmer IS 'Российский размер';
COMMENT ON COLUMN modeli.created_at IS 'Дата создания записи';
COMMENT ON COLUMN modeli.updated_at IS 'Дата последнего обновления';

-- Индексы для модели
CREATE INDEX idx_modeli_osnova ON modeli(model_osnova_id);
CREATE INDEX idx_modeli_importer ON modeli(importer_id);
CREATE INDEX idx_modeli_status ON modeli(status_id);

-- ============================================
-- 5. СКЛЕЙКИ МАРКЕТПЛЕЙСОВ
-- ============================================

-- Склейки Wildberries
CREATE TABLE skleyki_wb (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(100) NOT NULL UNIQUE,
    importer_id INT REFERENCES importery(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE skleyki_wb IS 'Склейки Wildberries - группировка карточек товаров на WB';
COMMENT ON COLUMN skleyki_wb.id IS 'Идентификатор склейки';
COMMENT ON COLUMN skleyki_wb.nazvanie IS 'Название склейки';
COMMENT ON COLUMN skleyki_wb.importer_id IS 'Импортер (ИП/ООО)';

-- Склейки Ozon
CREATE TABLE skleyki_ozon (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(100) NOT NULL UNIQUE,
    importer_id INT REFERENCES importery(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE skleyki_ozon IS 'Склейки Ozon - группировка карточек товаров на Ozon';
COMMENT ON COLUMN skleyki_ozon.id IS 'Идентификатор склейки';
COMMENT ON COLUMN skleyki_ozon.nazvanie IS 'Название склейки';
COMMENT ON COLUMN skleyki_ozon.importer_id IS 'Импортер (ИП/ООО)';

-- ============================================
-- 6. АРТИКУЛЫ (Модель + Цвет)
-- ============================================

CREATE TABLE artikuly (
    id SERIAL PRIMARY KEY,
    artikul VARCHAR(100) NOT NULL UNIQUE,
    model_id INT REFERENCES modeli(id),
    cvet_id INT REFERENCES cveta(id),
    status_id INT REFERENCES statusy(id),
    nomenklatura_wb BIGINT,
    artikul_ozon VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE artikuly IS 'Артикулы (модель в конкретном цвете)';
COMMENT ON COLUMN artikuly.id IS 'Идентификатор артикула';
COMMENT ON COLUMN artikuly.artikul IS 'Артикул (компбел-ж-бесшов/чер)';
COMMENT ON COLUMN artikuly.model_id IS 'Модель (FK)';
COMMENT ON COLUMN artikuly.cvet_id IS 'Цвет (FK на Color code)';
COMMENT ON COLUMN artikuly.status_id IS 'Статус артикула (FK)';
COMMENT ON COLUMN artikuly.nomenklatura_wb IS 'Номенклатура WB';
COMMENT ON COLUMN artikuly.artikul_ozon IS 'Артикул Ozon';
COMMENT ON COLUMN artikuly.created_at IS 'Дата создания записи';
COMMENT ON COLUMN artikuly.updated_at IS 'Дата последнего обновления';

-- Индексы для артикулов
CREATE INDEX idx_artikuly_model ON artikuly(model_id);
CREATE INDEX idx_artikuly_cvet ON artikuly(cvet_id);
CREATE INDEX idx_artikuly_status ON artikuly(status_id);
CREATE INDEX idx_artikuly_wb ON artikuly(nomenklatura_wb);

-- ============================================
-- 7. ТОВАРЫ/SKU (Конкретный размер)
-- ============================================

CREATE TABLE tovary (
    id SERIAL PRIMARY KEY,

    -- Баркоды
    barkod VARCHAR(20) NOT NULL UNIQUE,
    barkod_gs1 VARCHAR(20),
    barkod_gs2 VARCHAR(20),
    barkod_perehod VARCHAR(20),

    -- Связи
    artikul_id INT REFERENCES artikuly(id),
    razmer_id INT REFERENCES razmery(id),

    -- Статусы по каналам
    status_id INT REFERENCES statusy(id),
    status_ozon_id INT REFERENCES statusy(id),

    -- Идентификаторы маркетплейсов
    ozon_product_id BIGINT,
    ozon_fbo_sku_id BIGINT,
    lamoda_seller_sku VARCHAR(50),
    sku_china_size VARCHAR(50),

    -- Служебные поля
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE tovary IS 'Товары/SKU (из листа "Все товары") - конкретные баркоды';
COMMENT ON COLUMN tovary.id IS 'Идентификатор товара';
COMMENT ON COLUMN tovary.barkod IS 'Основной баркод';
COMMENT ON COLUMN tovary.barkod_gs1 IS 'БАРКОД GS1';
COMMENT ON COLUMN tovary.barkod_gs2 IS 'БАРКОД GS2';
COMMENT ON COLUMN tovary.barkod_perehod IS 'БАРКОД ПЕРЕХОД';
COMMENT ON COLUMN tovary.artikul_id IS 'Артикул (FK)';
COMMENT ON COLUMN tovary.razmer_id IS 'Размер (FK)';
COMMENT ON COLUMN tovary.status_id IS 'Статус товара (общий)';
COMMENT ON COLUMN tovary.status_ozon_id IS 'Статус товара OZON';
COMMENT ON COLUMN tovary.ozon_product_id IS 'Ozon Product ID';
COMMENT ON COLUMN tovary.ozon_fbo_sku_id IS 'FBO OZON SKU ID';
COMMENT ON COLUMN tovary.lamoda_seller_sku IS 'Seller SKU Lamoda';
COMMENT ON COLUMN tovary.sku_china_size IS 'SKU CHINA SIZE';
COMMENT ON COLUMN tovary.created_at IS 'Дата создания записи';
COMMENT ON COLUMN tovary.updated_at IS 'Дата последнего обновления';

-- Индексы для товаров
CREATE INDEX idx_tovary_artikul ON tovary(artikul_id);
CREATE INDEX idx_tovary_razmer ON tovary(razmer_id);
CREATE INDEX idx_tovary_status ON tovary(status_id);
CREATE INDEX idx_tovary_ozon ON tovary(ozon_product_id);

-- ============================================
-- 8. СВЯЗИ ТОВАРОВ СО СКЛЕЙКАМИ
-- ============================================

-- Связь товаров со склейками WB
CREATE TABLE tovary_skleyki_wb (
    tovar_id INT NOT NULL REFERENCES tovary(id) ON DELETE CASCADE,
    skleyka_id INT NOT NULL REFERENCES skleyki_wb(id) ON DELETE CASCADE,
    PRIMARY KEY (tovar_id, skleyka_id)
);
COMMENT ON TABLE tovary_skleyki_wb IS 'Связь товаров со склейками Wildberries';
COMMENT ON COLUMN tovary_skleyki_wb.tovar_id IS 'Товар (FK)';
COMMENT ON COLUMN tovary_skleyki_wb.skleyka_id IS 'Склейка WB (FK)';

-- Связь товаров со склейками Ozon
CREATE TABLE tovary_skleyki_ozon (
    tovar_id INT NOT NULL REFERENCES tovary(id) ON DELETE CASCADE,
    skleyka_id INT NOT NULL REFERENCES skleyki_ozon(id) ON DELETE CASCADE,
    PRIMARY KEY (tovar_id, skleyka_id)
);
COMMENT ON TABLE tovary_skleyki_ozon IS 'Связь товаров со склейками Ozon';
COMMENT ON COLUMN tovary_skleyki_ozon.tovar_id IS 'Товар (FK)';
COMMENT ON COLUMN tovary_skleyki_ozon.skleyka_id IS 'Склейка Ozon (FK)';

-- ============================================
-- 9. ИСТОРИЯ ИЗМЕНЕНИЙ (ВЕРСИОНИРОВАНИЕ)
-- ============================================

CREATE TABLE istoriya_izmeneniy (
    id SERIAL PRIMARY KEY,
    tablica VARCHAR(50) NOT NULL,
    zapis_id INT NOT NULL,
    pole VARCHAR(100),
    staroe_znachenie TEXT,
    novoe_znachenie TEXT,
    tip_operacii VARCHAR(20) NOT NULL CHECK (tip_operacii IN ('INSERT', 'UPDATE', 'DELETE')),
    polzovatel VARCHAR(100),
    data_izmeneniya TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE istoriya_izmeneniy IS 'История изменений - журнал всех изменений в спецификациях';
COMMENT ON COLUMN istoriya_izmeneniy.id IS 'Идентификатор записи';
COMMENT ON COLUMN istoriya_izmeneniy.tablica IS 'Название таблицы';
COMMENT ON COLUMN istoriya_izmeneniy.zapis_id IS 'ID измененной записи';
COMMENT ON COLUMN istoriya_izmeneniy.pole IS 'Название поля';
COMMENT ON COLUMN istoriya_izmeneniy.staroe_znachenie IS 'Старое значение';
COMMENT ON COLUMN istoriya_izmeneniy.novoe_znachenie IS 'Новое значение';
COMMENT ON COLUMN istoriya_izmeneniy.tip_operacii IS 'Тип операции: INSERT/UPDATE/DELETE';
COMMENT ON COLUMN istoriya_izmeneniy.polzovatel IS 'Кто изменил';
COMMENT ON COLUMN istoriya_izmeneniy.data_izmeneniya IS 'Когда изменено';

-- Индекс для быстрого поиска по истории
CREATE INDEX idx_istoriya_tablica ON istoriya_izmeneniy(tablica, zapis_id);
CREATE INDEX idx_istoriya_data ON istoriya_izmeneniy(data_izmeneniya);

-- ============================================
-- ПОЛЕЗНЫЕ ПРЕДСТАВЛЕНИЯ (VIEWS)
-- ============================================

-- Полная информация о товаре
CREATE OR REPLACE VIEW v_tovary_polnaya_info AS
SELECT
    t.id AS tovar_id,
    t.barkod,
    t.barkod_gs1,
    t.barkod_gs2,
    a.artikul,
    m.nazvanie AS model_nazvanie,
    m.kod AS model_kod,
    mo.kod AS model_osnova,
    c.color_code,
    c.cvet,
    c.color AS cvet_en,
    r.nazvanie AS razmer,
    k.nazvanie AS kategoriya,
    kol.nazvanie AS kollekciya,
    s.nazvanie AS status_tovara,
    i.nazvanie AS importer,
    mo.material,
    mo.sostav_syrya,
    t.ozon_product_id,
    t.ozon_fbo_sku_id,
    a.nomenklatura_wb
FROM tovary t
LEFT JOIN artikuly a ON t.artikul_id = a.id
LEFT JOIN modeli m ON a.model_id = m.id
LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
LEFT JOIN cveta c ON a.cvet_id = c.id
LEFT JOIN razmery r ON t.razmer_id = r.id
LEFT JOIN kategorii k ON mo.kategoriya_id = k.id
LEFT JOIN kollekcii kol ON mo.kollekciya_id = kol.id
LEFT JOIN statusy s ON t.status_id = s.id
LEFT JOIN importery i ON m.importer_id = i.id;

COMMENT ON VIEW v_tovary_polnaya_info IS 'Полная информация о товаре со всеми связями';

-- Статистика по моделям основы
CREATE OR REPLACE VIEW v_statistika_modeli_osnova AS
SELECT
    mo.id AS osnova_id,
    mo.kod AS osnova,
    k.nazvanie AS kategoriya,
    kol.nazvanie AS kollekciya,
    COUNT(DISTINCT m.id) AS kolichestvo_variaciy,
    COUNT(DISTINCT a.id) AS kolichestvo_artikulov,
    COUNT(DISTINCT t.id) AS kolichestvo_tovarov
FROM modeli_osnova mo
LEFT JOIN kategorii k ON mo.kategoriya_id = k.id
LEFT JOIN kollekcii kol ON mo.kollekciya_id = kol.id
LEFT JOIN modeli m ON m.model_osnova_id = mo.id
LEFT JOIN artikuly a ON a.model_id = m.id
LEFT JOIN tovary t ON t.artikul_id = a.id
GROUP BY mo.id, mo.kod, k.nazvanie, kol.nazvanie;

COMMENT ON VIEW v_statistika_modeli_osnova IS 'Статистика по моделям основы: количество вариаций, артикулов и товаров';

-- Статистика по моделям (вариациям)
CREATE OR REPLACE VIEW v_statistika_modeli AS
SELECT
    m.id AS model_id,
    m.kod,
    m.nazvanie,
    mo.kod AS model_osnova,
    i.nazvanie AS importer,
    s.nazvanie AS status,
    COUNT(DISTINCT a.id) AS kolichestvo_artikulov,
    COUNT(DISTINCT t.id) AS kolichestvo_tovarov,
    COUNT(DISTINCT c.id) AS kolichestvo_cvetov
FROM modeli m
LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
LEFT JOIN importery i ON m.importer_id = i.id
LEFT JOIN statusy s ON m.status_id = s.id
LEFT JOIN artikuly a ON a.model_id = m.id
LEFT JOIN tovary t ON t.artikul_id = a.id
LEFT JOIN cveta c ON a.cvet_id = c.id
GROUP BY m.id, m.kod, m.nazvanie, mo.kod, i.nazvanie, s.nazvanie;

COMMENT ON VIEW v_statistika_modeli IS 'Статистика по моделям: количество артикулов, товаров и цветов';

-- Статистика по цветам
CREATE OR REPLACE VIEW v_statistika_cveta AS
SELECT
    c.id AS cvet_id,
    c.color_code,
    c.cvet,
    c.color AS cvet_en,
    COUNT(DISTINCT a.id) AS kolichestvo_artikulov,
    COUNT(DISTINCT t.id) AS kolichestvo_tovarov,
    COUNT(DISTINCT m.id) AS kolichestvo_modeley
FROM cveta c
LEFT JOIN artikuly a ON a.cvet_id = c.id
LEFT JOIN tovary t ON t.artikul_id = a.id
LEFT JOIN modeli m ON a.model_id = m.id
GROUP BY c.id, c.color_code, c.cvet, c.color;

COMMENT ON VIEW v_statistika_cveta IS 'Статистика по цветам: количество артикулов, товаров и моделей';

-- Связь модель основа → модели (для проверки)
CREATE OR REPLACE VIEW v_modeli_po_osnove AS
SELECT
    mo.kod AS osnova,
    m.kod AS model_kod,
    m.nazvanie AS model_nazvanie,
    i.nazvanie AS importer,
    m.artikul_modeli,
    s.nazvanie AS status
FROM modeli_osnova mo
JOIN modeli m ON m.model_osnova_id = mo.id
LEFT JOIN importery i ON m.importer_id = i.id
LEFT JOIN statusy s ON m.status_id = s.id
ORDER BY mo.kod, m.kod;

COMMENT ON VIEW v_modeli_po_osnove IS 'Список моделей сгруппированных по модели основе';

-- ============================================
-- МАТРИЦА ЦВЕТОВ: Цвет → Модели основы
-- ============================================

-- Цвета с их моделями основы (главный VIEW для товарной матрицы)
CREATE OR REPLACE VIEW v_cveta_modeli_osnova AS
SELECT
    c.id AS cvet_id,
    c.color_code,
    c.cvet,
    c.color AS cvet_en,
    sc.nazvanie AS status_cveta,
    COUNT(DISTINCT mo.id) AS kolichestvo_modeley,
    STRING_AGG(DISTINCT mo.kod, ', ' ORDER BY mo.kod) AS modeli_osnova,
    COUNT(DISTINCT a.id) AS kolichestvo_artikulov,
    COUNT(DISTINCT t.id) AS kolichestvo_sku
FROM cveta c
LEFT JOIN statusy sc ON c.status_id = sc.id
LEFT JOIN artikuly a ON a.cvet_id = c.id
LEFT JOIN modeli m ON a.model_id = m.id
LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
LEFT JOIN tovary t ON t.artikul_id = a.id
GROUP BY c.id, c.color_code, c.cvet, c.color, sc.nazvanie
ORDER BY c.color_code;

COMMENT ON VIEW v_cveta_modeli_osnova IS 'Матрица цветов: какой цвет в каких моделях основы представлен';

-- Детальная связь: конкретные артикулы по цветам
CREATE OR REPLACE VIEW v_artikuly_po_cvetam AS
SELECT
    c.color_code,
    c.cvet,
    mo.kod AS model_osnova,
    m.kod AS model,
    m.nazvanie AS model_nazvanie,
    a.artikul,
    a.nomenklatura_wb,
    sa.nazvanie AS status_artikula,
    COUNT(DISTINCT t.id) AS kolichestvo_sku
FROM cveta c
JOIN artikuly a ON a.cvet_id = c.id
JOIN modeli m ON a.model_id = m.id
JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
LEFT JOIN tovary t ON t.artikul_id = a.id
LEFT JOIN statusy sa ON a.status_id = sa.id
GROUP BY c.color_code, c.cvet, mo.kod, m.kod, m.nazvanie, a.artikul, a.nomenklatura_wb, sa.nazvanie
ORDER BY c.color_code, mo.kod, m.kod;

COMMENT ON VIEW v_artikuly_po_cvetam IS 'Детальный список артикулов сгруппированный по цветам';

-- Pivot: какие цвета в какой модели основе (только наличие)
CREATE OR REPLACE VIEW v_matrica_cveta_modeli AS
SELECT
    c.color_code,
    c.cvet,
    MAX(CASE WHEN mo.kod = 'Vuki' THEN '✓' ELSE '' END) AS "Vuki",
    MAX(CASE WHEN mo.kod = 'Moon' THEN '✓' ELSE '' END) AS "Moon",
    MAX(CASE WHEN mo.kod = 'Ruby' THEN '✓' ELSE '' END) AS "Ruby",
    MAX(CASE WHEN mo.kod = 'Joy' THEN '✓' ELSE '' END) AS "Joy",
    MAX(CASE WHEN mo.kod = 'Space' THEN '✓' ELSE '' END) AS "Space",
    MAX(CASE WHEN mo.kod = 'Alice' THEN '✓' ELSE '' END) AS "Alice",
    MAX(CASE WHEN mo.kod = 'Wendy' THEN '✓' ELSE '' END) AS "Wendy",
    MAX(CASE WHEN mo.kod = 'Audrey' THEN '✓' ELSE '' END) AS "Audrey",
    MAX(CASE WHEN mo.kod = 'Set Vuki' THEN '✓' ELSE '' END) AS "SetVuki",
    MAX(CASE WHEN mo.kod = 'Set Moon' THEN '✓' ELSE '' END) AS "SetMoon",
    MAX(CASE WHEN mo.kod = 'Set Ruby' THEN '✓' ELSE '' END) AS "SetRuby"
FROM cveta c
LEFT JOIN artikuly a ON a.cvet_id = c.id
LEFT JOIN modeli m ON a.model_id = m.id
LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
GROUP BY c.color_code, c.cvet
ORDER BY c.color_code;

COMMENT ON VIEW v_matrica_cveta_modeli IS 'Pivot-матрица цветов по моделям (для визуализации товарной матрицы)';

-- Трикотажная коллекция: цвета которые есть не во всех 4 моделях
CREATE OR REPLACE VIEW v_tricot_nepolnye_cveta AS
WITH tricot_cveta AS (
    SELECT
        c.color_code,
        c.cvet,
        COUNT(DISTINCT CASE WHEN mo.kod = 'Vuki' THEN 1 END) AS has_vuki,
        COUNT(DISTINCT CASE WHEN mo.kod = 'Moon' THEN 1 END) AS has_moon,
        COUNT(DISTINCT CASE WHEN mo.kod = 'Ruby' THEN 1 END) AS has_ruby,
        COUNT(DISTINCT CASE WHEN mo.kod = 'Joy' THEN 1 END) AS has_joy
    FROM cveta c
    JOIN artikuly a ON a.cvet_id = c.id
    JOIN modeli m ON a.model_id = m.id
    JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
    WHERE mo.kod IN ('Vuki', 'Moon', 'Ruby', 'Joy')
    GROUP BY c.color_code, c.cvet
)
SELECT
    color_code,
    cvet,
    CASE WHEN has_vuki > 0 THEN '✓' ELSE '✗' END AS "Vuki",
    CASE WHEN has_moon > 0 THEN '✓' ELSE '✗' END AS "Moon",
    CASE WHEN has_ruby > 0 THEN '✓' ELSE '✗' END AS "Ruby",
    CASE WHEN has_joy > 0 THEN '✓' ELSE '✗' END AS "Joy",
    (has_vuki + has_moon + has_ruby + has_joy) AS vsego_modeley,
    CASE
        WHEN (has_vuki + has_moon + has_ruby + has_joy) = 4 THEN 'Полный'
        WHEN (has_vuki + has_moon + has_ruby + has_joy) = 0 THEN 'Нет в трикотаже'
        ELSE 'Неполный'
    END AS sostoyanie
FROM tricot_cveta
WHERE (has_vuki + has_moon + has_ruby + has_joy) BETWEEN 1 AND 3
ORDER BY (has_vuki + has_moon + has_ruby + has_joy) DESC, color_code;

COMMENT ON VIEW v_tricot_nepolnye_cveta IS 'Цвета трикотажной коллекции которые есть НЕ во всех 4 моделях (Vuki, Moon, Ruby, Joy)';
