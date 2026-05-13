/**
 * W9.5 — единые каталоги колонок для всех трёх реестров.
 *
 * Принцип:
 * - В `default: true` помечены ТЕКУЩИЕ дефолт-видимые колонки (то, что
 *   пользователь видит сейчас) — чтобы апгрейд не ломал привычный UX.
 * - Дополнительные поля из БД (artikuly/sku/modeli_osnova) добавлены, но
 *   `default: false` — пользователь может включить их через конфигуратор.
 * - Источник истины по схеме — Supabase MCP `list_tables` (см. ТЗ W9.5).
 */

import type { ColumnDescriptor } from "@/hooks/use-column-config"

// ───────────────────────────────────────────────────────────────────────────
// MATRIX (modeli_osnova) — реестр базовых моделей.
// ───────────────────────────────────────────────────────────────────────────
// Текущая матрица в коде использует header-labels из MODEL_COLUMNS массива в
// matrix.tsx; здесь — расширенный набор полей из БД modeli_osnova для
// конфигуратора видимости.

export const MATRIX_COLUMNS: ColumnDescriptor[] = [
  { key: "nazvanie",        label: "Название",       default: true,  group: "Основные" },
  { key: "kod",             label: "Код",            default: false, group: "Основные" },
  { key: "brand",           label: "Бренд",          default: true,  group: "Основные" },
  { key: "kategoriya",      label: "Категория",      default: true,  group: "Основные" },
  { key: "kollekciya",      label: "Коллекция",      default: true,  group: "Основные" },
  { key: "tip_kollekcii",   label: "Тип коллекции",  default: false, group: "Основные" },
  { key: "fabrika",         label: "Фабрика",        default: true,  group: "Основные" },
  { key: "status",          label: "Статус",         default: true,  group: "Основные" },
  { key: "razmery",         label: "Размеры",        default: true,  group: "Основные" },
  { key: "cveta",           label: "Цвета",          default: true,  group: "Основные" },
  { key: "completeness",    label: "Заполн.",        default: true,  group: "Основные" },
  { key: "cv_art_sku",      label: "Цв / Арт / SKU", default: true,  group: "Основные" },
  { key: "obnovleno",       label: "Обновлено",      default: true,  group: "Основные" },
  // Расширенные поля modeli_osnova — скрыты по умолчанию.
  { key: "nazvanie_etiketka", label: "Название (этикетка)", default: false, group: "Идентификация" },
  { key: "nazvanie_sayt",     label: "Название (сайт)",     default: false, group: "Идентификация" },
  { key: "sku_china",         label: "SKU Китай",           default: false, group: "Идентификация" },
  { key: "tnved",             label: "ТН ВЭД",              default: false, group: "Идентификация" },
  { key: "gruppa_sertifikata",label: "Группа сертификата",  default: false, group: "Идентификация" },
  { key: "upakovka",          label: "Упаковка",            default: false, group: "Упаковка" },
  { key: "ves_kg",            label: "Вес, кг",             default: false, group: "Упаковка" },
  { key: "dlina_cm",          label: "Длина, см",           default: false, group: "Упаковка" },
  { key: "shirina_cm",        label: "Ширина, см",          default: false, group: "Упаковка" },
  { key: "vysota_cm",         label: "Высота, см",          default: false, group: "Упаковка" },
  { key: "kratnost_koroba",   label: "Кратность короба",    default: false, group: "Упаковка" },
  { key: "srok_proizvodstva", label: "Срок производства",   default: false, group: "Производство" },
  { key: "komplektaciya",     label: "Комплектация",        default: false, group: "Производство" },
  { key: "material",          label: "Материал",            default: false, group: "Состав" },
  { key: "sostav_syrya",      label: "Состав сырья",        default: false, group: "Состав" },
  { key: "composition",       label: "Composition (EN)",    default: false, group: "Состав" },
  { key: "dlya_kakoy_grudi",  label: "Для какой груди",     default: false, group: "Атрибуты белья" },
  { key: "stepen_podderzhki", label: "Степень поддержки",   default: false, group: "Атрибуты белья" },
  { key: "forma_chashki",     label: "Форма чашки",         default: false, group: "Атрибуты белья" },
  { key: "regulirovka",       label: "Регулировка",         default: false, group: "Атрибуты белья" },
  { key: "zastezhka",         label: "Застёжка",            default: false, group: "Атрибуты белья" },
  { key: "posadka_trusov",    label: "Посадка трусов",      default: false, group: "Атрибуты белья" },
  { key: "vid_trusov",        label: "Вид трусов",          default: false, group: "Атрибуты белья" },
  { key: "naznachenie",       label: "Назначение",          default: false, group: "Маркетинг" },
  { key: "stil",              label: "Стиль",               default: false, group: "Маркетинг" },
  { key: "po_nastroeniyu",    label: "По настроению",       default: false, group: "Маркетинг" },
  { key: "tegi",              label: "Теги",                default: false, group: "Маркетинг" },
  { key: "opisanie_sayt",     label: "Описание (сайт)",     default: false, group: "Маркетинг" },
  { key: "description",       label: "Description (EN)",    default: false, group: "Маркетинг" },
  { key: "details",           label: "Details",             default: false, group: "Маркетинг" },
  { key: "notion_link",       label: "Notion",              default: false, group: "Ссылки" },
  { key: "notion_strategy_link", label: "Notion (стратегия)", default: false, group: "Ссылки" },
  { key: "yandex_disk_link",  label: "Я.Диск",              default: false, group: "Ссылки" },
  { key: "header_image_url",  label: "Header image URL",    default: false, group: "Ссылки" },
  { key: "created_at",        label: "Создано",             default: false, group: "Системные" },
]

// ───────────────────────────────────────────────────────────────────────────
// ARTIKULY — реестр артикулов.
// ───────────────────────────────────────────────────────────────────────────

export const ARTIKULY_COLUMNS_FULL: ColumnDescriptor[] = [
  { key: "artikul",      label: "Артикул",         default: true,  group: "Основные" },
  { key: "model",        label: "Модель",          default: true,  group: "Основные" },
  { key: "cvet",         label: "Цвет",            default: true,  group: "Основные" },
  { key: "status",       label: "Статус артикула", default: true,  group: "Основные" },
  { key: "wb_nom",       label: "WB-номенклатура", default: true,  group: "Маркетплейсы", badge: "WB" },
  { key: "ozon_art",     label: "OZON-артикул",    default: true,  group: "Маркетплейсы", badge: "OZON" },
  { key: "kategoriya",   label: "Категория",       default: true,  group: "Метаданные" },
  { key: "kollekciya",   label: "Коллекция",       default: true,  group: "Метаданные" },
  { key: "fabrika",      label: "Производитель",   default: true,  group: "Метаданные" },
  { key: "created",      label: "Создан",          default: true,  group: "Системные" },
  { key: "updated",      label: "Обновлён",        default: true,  group: "Системные" },
  // Расширения W9.5 — поля из artikuly + связанных таблиц.
  { key: "model_kod",       label: "Вариация (kod)",   default: false, group: "Идентификация" },
  { key: "nazvanie_etiketka", label: "Название (этикетка)", default: false, group: "Идентификация" },
  { key: "cvet_ru",         label: "Цвет (RU)",        default: false, group: "Цвет" },
  { key: "cvet_en",         label: "Цвет (EN)",        default: false, group: "Цвет" },
  { key: "cvet_color_code", label: "Цвет (код)",       default: false, group: "Цвет" },
  { key: "tovary_cnt",      label: "SKU (шт)",         default: false, group: "Связи" },
  // W10.26 — склейка артикула (WB и/или OZON).  По умолчанию выключена —
  // данные подгружаются отдельным запросом, не нагружаем основной fetch если
  // колонка скрыта (хук в artikuly.tsx сам решает делать fetch или нет).
  { key: "skleyka",         label: "Склейка",          default: false, group: "Связи" },
]

// ───────────────────────────────────────────────────────────────────────────
// TOVARY (SKU) — реестр товаров.
// ───────────────────────────────────────────────────────────────────────────

export const TOVARY_COLUMNS_FULL: ColumnDescriptor[] = [
  { key: "barkod",         label: "Баркод",          default: true,  group: "Основные" },
  { key: "artikul",        label: "Артикул",         default: true,  group: "Основные" },
  { key: "model",          label: "Модель",          default: true,  group: "Основные" },
  { key: "cvet",           label: "Цвет",            default: true,  group: "Основные" },
  { key: "razmer",         label: "Размер",          default: true,  group: "Основные" },
  { key: "wb_nom",         label: "WB-номенклатура", default: true,  group: "Маркетплейсы", badge: "WB" },
  { key: "ozon_art",       label: "OZON-артикул",    default: true,  group: "Маркетплейсы", badge: "OZON" },
  { key: "status_wb",      label: "Статус WB",       default: true,  group: "Статусы", badge: "канал" },
  { key: "status_ozon",    label: "Статус OZON",     default: true,  group: "Статусы", badge: "канал" },
  { key: "status_sayt",    label: "Статус Сайт",     default: true,  group: "Статусы", badge: "канал" },
  { key: "status_lamoda",  label: "Статус Lamoda",   default: true,  group: "Статусы", badge: "канал" },
  { key: "barkod_gs1",     label: "Баркод GS1",      default: true,  group: "Баркоды" },
  { key: "barkod_gs2",     label: "Баркод GS2",      default: true,  group: "Баркоды" },
  { key: "barkod_perehod", label: "Баркод перехода", default: true,  group: "Баркоды" },
  { key: "cena_wb",        label: "Цена WB",         default: true,  group: "Цены" },
  { key: "cena_ozon",      label: "Цена OZON",       default: true,  group: "Цены" },
  { key: "created",        label: "Дата создания",   default: true,  group: "Системные" },
  // Расширения W9.5 — недостающие поля из tovary + связанных таблиц.
  { key: "sku_china_size",   label: "SKU Китай (размер)", default: false, group: "Идентификация" },
  { key: "ozon_product_id",  label: "OZON product_id",    default: false, group: "Маркетплейсы", badge: "OZON" },
  { key: "ozon_fbo_sku_id",  label: "OZON FBO SKU",       default: false, group: "Маркетплейсы", badge: "OZON" },
  { key: "lamoda_seller_sku",label: "Lamoda seller SKU",  default: false, group: "Маркетплейсы", badge: "Lamoda" },
  { key: "kollekciya",       label: "Коллекция",          default: false, group: "Метаданные" },
  { key: "kategoriya",       label: "Категория",          default: false, group: "Метаданные" },
  // W10.26 — склейка SKU (WB и/или OZON), JOIN на tovary_skleyki_*.
  { key: "skleyka",          label: "Склейка",            default: false, group: "Связи" },
  // TODO(W9.5-followup): `updated_at` есть в tovary в БД, но не выбирается в
  // fetchTovaryRegistry — добавить, если потребуется. Пока скрыто.
]
