// W9.19 — единый компонент empty-state для каталога.
//
// Используется во всех местах, где список/таблица оказывается пустым:
//   • реестры (/catalog, /catalog/artikuly, /catalog/tovary)
//   • карточка модели (вкладки Атрибуты / Артикулы / SKU)
//   • любые drawer/детальные представления
//
// Различает два сценария:
//   1) реальных данных нет          → "Создать первое" CTA
//   2) применены фильтры / поиск    → "Сбросить фильтры" secondary CTA
//
// API:
//   <EmptyState
//       icon={<Package />}
//       title="Нет моделей"
//       description="Создайте первую модель, чтобы начать наполнять каталог."
//       cta={{ label: "+ Новая модель", onClick: () => setOpen(true) }}
//       secondaryCta={{ label: "Сбросить фильтры", onClick: () => resetFilters() }}
//   />
//
// Layout: централизованный flex, padding 80px+, muted-цвет, иконка 48px,
// CTA — primary stone-900 кнопка, secondaryCta — нейтральная.

import type { ReactNode } from "react"

export interface EmptyStateAction {
  label: string
  onClick: () => void
}

export interface EmptyStateProps {
  /** Опциональная иконка (lucide-react рекомендуется, размер 48×48). */
  icon?: ReactNode
  /** Главный заголовок. Кратко описывает что отсутствует. */
  title: string
  /** Подсказка под заголовком (1-2 предложения, муtted). */
  description?: string
  /** Primary CTA — главное действие пользователя. */
  cta?: EmptyStateAction
  /** Вторая кнопка (например, "Сбросить фильтры"). */
  secondaryCta?: EmptyStateAction
  /** Доп. класс для контейнера (например, чтобы вместить внутри таблицы). */
  className?: string
}

/**
 * EmptyState — централизованный плейсхолдер для пустых списков каталога.
 *
 * Padding 80px+ по вертикали даёт визуальный вес, чтобы пустое состояние
 * не выглядело как "что-то сломалось". Иконка 48px — фокус-точка над текстом.
 */
export function EmptyState({
  icon,
  title,
  description,
  cta,
  secondaryCta,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center px-6 py-20 ${className ?? ""}`}
    >
      {icon && (
        <div
          className="mb-4 flex items-center justify-center text-stone-300"
          style={{ width: 48, height: 48 }}
          aria-hidden="true"
        >
          {icon}
        </div>
      )}
      <h3 className="text-base font-medium text-stone-800 mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-stone-500 max-w-md mb-5">{description}</p>
      )}
      {(cta || secondaryCta) && (
        <div className="flex items-center gap-2">
          {cta && (
            <button
              type="button"
              onClick={cta.onClick}
              className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md transition-colors"
            >
              {cta.label}
            </button>
          )}
          {secondaryCta && (
            <button
              type="button"
              onClick={secondaryCta.onClick}
              className="px-3 py-1.5 text-xs text-stone-700 bg-white border border-stone-200 hover:bg-stone-50 rounded-md transition-colors"
            >
              {secondaryCta.label}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
