-- database/migrations/030_catalog_export_views.sql
-- 6 экспортных view для синка Hub → Google Sheets (mirror).
-- Каждое view возвращает колонки в том порядке и с теми именами,
-- что в шапках листов "Спецификация Wookiee — Зеркало Hub"
-- (spreadsheet 1qqcCmg-Xagike1G3F3TdBihEDFF6mMLiDiZPXXWR7ls).

-- =========================================================================
-- 1. vw_export_modeli  — одна строка на каждую запись из public.modeli
--    anchor: "Модель"
-- =========================================================================

create or replace view public.vw_export_modeli
    with (security_invoker = true) as
select
    m.kod                              as "Модель",
    mo.kod                             as "Модель основа",
    m.nazvanie                         as "Название модели",
    m.nazvanie_en                      as "Название EN",
    m.artikul_modeli                   as "Артикул модели",
    b.nazvanie                         as "Бренд",
    k.nazvanie                         as "Категория",
    coll.nazvanie                      as "Коллекция",
    tk.nazvanie                        as "Тип коллекции",
    f.nazvanie                         as "Фабрика",
    s.nazvanie                         as "Статус",
    m.rossiyskiy_razmer                as "Российский размер",
    mo.razmery_modeli                  as "Размеры модели",
    case when m.nabor then 'Да' else 'Нет' end as "Набор",
    mo.tegi                            as "Теги",
    mo.posadka_trusov                  as "Посадка трусов",
    mo.vid_trusov                      as "Вид трусов",
    mo.dlya_kakoy_grudi                as "Для какой груди",
    mo.stepen_podderzhki               as "Степень поддержки",
    mo.forma_chashki                   as "Форма чашки",
    mo.regulirovka                     as "Регулировка",
    mo.zastezhka                       as "Застежка",
    mo.naznachenie                     as "Назначение",
    mo.stil                            as "Стиль",
    mo.po_nastroeniyu                  as "По настроению",
    mo.material                        as "Материал",
    mo.sostav_syrya                    as "Состав сырья",
    mo.composition                     as "Composition",
    mo.tnved                           as "ТНВЭД",
    mo.gruppa_sertifikata              as "Группа сертификата",
    mo.nazvanie_etiketka               as "Название для этикетки",
    mo.nazvanie_sayt                   as "Название для сайта",
    mo.opisanie_sayt                   as "Описание для сайта",
    mo.details                         as "Details",
    mo.description                     as "Description",
    mo.sku_china                       as "SKU CHINA",
    mo.upakovka                        as "Упаковка",
    mo.ves_kg                          as "Вес (кг)",
    mo.dlina_cm                        as "Длина",
    mo.shirina_cm                      as "Ширина",
    mo.vysota_cm                       as "Высота",
    mo.kratnost_koroba                 as "Кратность короба",
    mo.srok_proizvodstva               as "Срок производства",
    mo.komplektaciya                   as "Комплектация",
    mo.notion_link                     as "Notion link",
    mo.notion_strategy_link            as "Notion strategy link",
    mo.yandex_disk_link                as "Yandex disk link",
    mo.header_image_url                as "Header image URL"
from public.modeli m
left join public.modeli_osnova    mo  on mo.id  = m.model_osnova_id
left join public.brendy           b   on b.id   = mo.brand_id
left join public.kategorii        k   on k.id   = mo.kategoriya_id
left join public.kollekcii        coll on coll.id = mo.kollekciya_id
left join public.tipy_kollekciy   tk  on tk.id  = mo.tip_kollekcii_id
left join public.fabriki          f   on f.id   = mo.fabrika_id
left join public.statusy          s   on s.id   = m.status_id;

-- =========================================================================
-- 2. vw_export_artikuly  — одна строка на каждый артикул
--    anchor: "Артикул"
-- =========================================================================

create or replace view public.vw_export_artikuly
    with (security_invoker = true) as
select
    a.artikul              as "Артикул",
    m.kod                  as "Модель",
    c.color_code           as "Color code",
    c.cvet                 as "Цвет",
    c.color                as "Color",
    c.hex                  as "HEX",
    c.semeystvo            as "Семейство",
    s.nazvanie             as "Статус",
    a.nomenklatura_wb      as "Номенклатура WB",
    a.artikul_ozon         as "Артикул Ozon"
from public.artikuly a
left join public.modeli  m on m.id = a.model_id
left join public.cveta   c on c.id = a.cvet_id
left join public.statusy s on s.id = a.status_id;

-- =========================================================================
-- 3. vw_export_tovary  — одна строка на каждый товар (баркод)
--    anchor: "БАРКОД"
-- =========================================================================

create or replace view public.vw_export_tovary
    with (security_invoker = true) as
select
    t.barkod                as "БАРКОД",
    t.barkod_gs1            as "БАРКОД GS1",
    t.barkod_gs2            as "БАРКОД GS2",
    t.barkod_perehod        as "БАРКОД ПЕРЕХОД",
    a.artikul               as "Артикул",
    m.kod                   as "Модель",
    c.color_code            as "Color code",
    c.cvet                  as "Цвет",
    c.color                 as "Color",
    r.nazvanie              as "Размер",
    r.ru                    as "Российский размер",
    s_wb.nazvanie           as "Статус товара",
    s_oz.nazvanie           as "Статус товара OZON",
    s_st.nazvanie           as "Статус товара Сайт",
    s_lm.nazvanie           as "Статус товара Lamoda",
    t.ozon_product_id       as "Ozon Product ID",
    t.ozon_fbo_sku_id       as "FBO OZON SKU ID",
    a.artikul_ozon          as "Артикул Ozon",
    t.lamoda_seller_sku     as "Seller SKU Lamoda",
    t.sku_china_size        as "SKU CHINA SIZE",
    a.nomenklatura_wb       as "Номенклатура WB"
from public.tovary t
left join public.artikuly a   on a.id = t.artikul_id
left join public.modeli   m   on m.id = a.model_id
left join public.cveta    c   on c.id = a.cvet_id
left join public.razmery  r   on r.id = t.razmer_id
left join public.statusy  s_wb on s_wb.id = t.status_id
left join public.statusy  s_oz on s_oz.id = t.status_ozon_id
left join public.statusy  s_st on s_st.id = t.status_sayt_id
left join public.statusy  s_lm on s_lm.id = t.status_lamoda_id;

-- =========================================================================
-- 4. vw_export_cveta  — справочник цветов
--    anchor: "Color code"
-- =========================================================================

create or replace view public.vw_export_cveta
    with (security_invoker = true) as
select
    c.color_code   as "Color code",
    c.color        as "Color",
    c.cvet         as "Цвет",
    c.hex          as "HEX",
    s.nazvanie     as "Статус",
    c.semeystvo    as "Семейство",
    c.lastovica    as "Ластовица"
from public.cveta c
left join public.statusy s on s.id = c.status_id;

-- =========================================================================
-- 5. vw_export_skleyki_wb  — одна строка на каждое вхождение SKU в склейку WB
--    anchor: ("Название склейки", "БАРКОД")
-- =========================================================================

create or replace view public.vw_export_skleyki_wb
    with (security_invoker = true) as
select
    sw.nazvanie     as "Название склейки",
    t.barkod        as "БАРКОД",
    a.artikul       as "Артикул",
    m.kod           as "Модель",
    c.color_code    as "Color code",
    c.cvet          as "Цвет",
    r.nazvanie      as "Размер",
    'WB'::text      as "Канал",
    to_char(sw.created_at at time zone 'UTC', 'YYYY-MM-DD HH24:MI:SS') as "Создано"
from public.tovary_skleyki_wb tsw
join      public.skleyki_wb  sw on sw.id = tsw.skleyka_id
join      public.tovary      t  on t.id  = tsw.tovar_id
left join public.artikuly    a  on a.id  = t.artikul_id
left join public.modeli      m  on m.id  = a.model_id
left join public.cveta       c  on c.id  = a.cvet_id
left join public.razmery     r  on r.id  = t.razmer_id;

-- =========================================================================
-- 6. vw_export_skleyki_ozon  — одна строка на каждое вхождение SKU в склейку Ozon
--    anchor: ("Название склейки", "БАРКОД")
-- =========================================================================

create or replace view public.vw_export_skleyki_ozon
    with (security_invoker = true) as
select
    so.nazvanie     as "Название склейки",
    t.barkod        as "БАРКОД",
    a.artikul       as "Артикул",
    m.kod           as "Модель",
    c.color_code    as "Color code",
    c.cvet          as "Цвет",
    r.nazvanie      as "Размер",
    'OZON'::text    as "Канал",
    to_char(so.created_at at time zone 'UTC', 'YYYY-MM-DD HH24:MI:SS') as "Создано"
from public.tovary_skleyki_ozon tso
join      public.skleyki_ozon so on so.id = tso.skleyka_id
join      public.tovary       t  on t.id  = tso.tovar_id
left join public.artikuly     a  on a.id  = t.artikul_id
left join public.modeli       m  on m.id  = a.model_id
left join public.cveta        c  on c.id  = a.cvet_id
left join public.razmery      r  on r.id  = t.razmer_id;

-- =========================================================================
-- Grants: views inherit RLS from the underlying tables (RLS is enforced by
-- Postgres when querying through views unless `security_invoker` is set).
-- We need service_role + authenticated to be able to SELECT.
-- =========================================================================

grant select on public.vw_export_modeli       to service_role, authenticated;
grant select on public.vw_export_artikuly     to service_role, authenticated;
grant select on public.vw_export_tovary       to service_role, authenticated;
grant select on public.vw_export_cveta        to service_role, authenticated;
grant select on public.vw_export_skleyki_wb   to service_role, authenticated;
grant select on public.vw_export_skleyki_ozon to service_role, authenticated;

-- Explicitly revoke from anon (defence in depth).
revoke all on public.vw_export_modeli       from anon;
revoke all on public.vw_export_artikuly     from anon;
revoke all on public.vw_export_tovary       from anon;
revoke all on public.vw_export_cveta        from anon;
revoke all on public.vw_export_skleyki_wb   from anon;
revoke all on public.vw_export_skleyki_ozon from anon;

-- =========================================================================
-- Register the new sheets-mirror sync tool in public.tools so tool_runs
-- inserts via shared.tool_logger don't violate the FK.
-- =========================================================================

insert into public.tools (slug, name_ru, display_name, type, category, description, status)
values (
    'catalog-sheets-mirror',
    'Зеркало каталога в Google Sheets',
    'Catalog Sheets Mirror',
    'service',
    'infra',
    'Hub → Google Sheets синк: пишет состояние каталога из Supabase в зеркальную таблицу.',
    'active'
)
on conflict (slug) do update set
    name_ru = excluded.name_ru,
    description = excluded.description,
    status = excluded.status,
    updated_at = now();
