// W10.16 — Русские лейблы для сегментов URL каталога.
//
// Раньше маппинг slug → label жил инлайн в `catalog-topbar.tsx`
// (`BREADCRUMB_MAP`). При появлении новых страниц (например, /references/brendy
// или /references/tipy-kollekciy) лейбл забывали добавить, и в хлебных крошках
// светился сырой slug `tipy-kollekciy` вместо «Типы коллекций».
//
// Вынесли в отдельный модуль, чтобы:
//   1. Можно было реиспользовать в нескольких местах (top-bar, sidebar tooltips,
//      и любые другие точки рендера пути).
//   2. Падение на неизвестный slug было предсказуемым (fallback на сам slug).
//   3. При добавлении нового раздела каталога — было единое место правки.

export const ROUTE_LABELS: Record<string, string> = {
  // Контент
  matrix: "Матрица",
  artikuly: "Артикулы",
  tovary: "Товары/SKU",
  skleyki: "Склейки",
  colors: "Цвета",
  // Справочники
  references: "Справочники",
  brendy: "Бренды",
  kategorii: "Категории",
  kollekcii: "Коллекции",
  "tipy-kollekciy": "Типы коллекций",
  fabriki: "Производители",
  importery: "Юрлица",
  razmery: "Размеры",
  statusy: "Статусы",
  "semeystva-cvetov": "Семейства цветов",
  upakovki: "Упаковки",
  "kanaly-prodazh": "Каналы продаж",
  sertifikaty: "Сертификаты",
  atributy: "Атрибуты",
  // Операции
  import: "Импорт CSV",
  catalog: "Каталог",
  // Служебное
  __demo__: "UI Demo",
}

/**
 * Возвращает человекочитаемое название для URL-сегмента.
 * Если slug неизвестен — возвращаем сам slug (как fallback для динамических
 * сегментов — например, `?model=KOD` или код карточки в URL).
 */
export function getRouteLabel(slug: string): string {
  return ROUTE_LABELS[slug] ?? slug
}
