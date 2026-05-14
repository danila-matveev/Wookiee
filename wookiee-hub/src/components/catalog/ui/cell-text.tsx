import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react"
import * as RTooltip from "@radix-ui/react-tooltip"
import { cn } from "@/lib/utils"

interface CellTextProps {
  children: ReactNode
  /**
   * `1` (default) — single-line ellipsis (`text-overflow: ellipsis; white-space: nowrap`).
   * `2` — multi-line clamp через `-webkit-line-clamp`.
   */
  clamp?: 1 | 2
  /** Дополнительные классы для контейнера. */
  className?: string
  /**
   * Текст для tooltip-а. Если не указан и `children` — строка/число, тултип покажет
   * `String(children)`. Если указан — используется явно (полезно для богатого children-а).
   */
  title?: string
  /** Опциональный max-width override. По умолчанию ячейка наследует ширину `<td>`. */
  maxWidth?: number | string
}

/**
 * CellText — обрезание длинного текста в ячейках таблиц + tooltip на hover, когда
 * содержимое реально не помещается. Используй внутри `<td>`, оборачивая текстовое
 * содержимое; не нужно для статус-бейджей, цветовых свотчей, кнопок и т.п.
 *
 * Поведение:
 * - `clamp=1` (default): одна строка, `text-overflow: ellipsis`, `white-space: nowrap`.
 * - `clamp=2`: до двух строк через `-webkit-line-clamp` (для комментариев).
 * - Tooltip появляется только если `scrollWidth > clientWidth` (clamp=1) или
 *   `scrollHeight > clientHeight` (clamp=2) — то есть, контент реально обрезан.
 *
 * W9.15 — общий компонент для всех таблиц каталога (matrix / artikuly / tovary /
 * model-card). Сохраняет API tooltip-а из `@/components/catalog/ui/tooltip.tsx`
 * (Radix + stone-900 fill, 11px text).
 */
export function CellText({
  children,
  clamp = 1,
  className,
  title,
  maxWidth,
}: CellTextProps) {
  const ref = useRef<HTMLSpanElement | null>(null)
  const [overflowing, setOverflowing] = useState(false)

  // Авто-детект обрезания. Запускаем после mount + следим за изменением children/clamp.
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    if (clamp === 1) {
      setOverflowing(el.scrollWidth > el.clientWidth + 1)
    } else {
      setOverflowing(el.scrollHeight > el.clientHeight + 1)
    }
  }, [children, clamp])

  // Перепроверять при resize окна (не критично, но дешёво).
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const onResize = () => {
      if (clamp === 1) {
        setOverflowing(el.scrollWidth > el.clientWidth + 1)
      } else {
        setOverflowing(el.scrollHeight > el.clientHeight + 1)
      }
    }
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [clamp])

  const clampStyles: CSSProperties =
    clamp === 1
      ? {
          display: "block",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          minWidth: 0,
          maxWidth: maxWidth ?? "100%",
        }
      : {
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical" as const,
          overflow: "hidden",
          minWidth: 0,
          maxWidth: maxWidth ?? "100%",
          wordBreak: "break-word",
        }

  // Текст tooltip-а: явный prop > строковый children > пусто.
  const tooltipText =
    title ??
    (typeof children === "string" || typeof children === "number"
      ? String(children)
      : "")

  const content = (
    <span ref={ref} className={cn("align-middle", className)} style={clampStyles}>
      {children}
    </span>
  )

  if (!overflowing || !tooltipText) {
    return content
  }

  return (
    <RTooltip.Provider delayDuration={150} skipDelayDuration={100}>
      <RTooltip.Root>
        <RTooltip.Trigger asChild>{content}</RTooltip.Trigger>
        <RTooltip.Portal>
          <RTooltip.Content
            side="top"
            align="center"
            sideOffset={6}
            collisionPadding={8}
            avoidCollisions
            className={cn(
              "z-50 px-2 py-1 bg-stone-900 text-white text-[11px] rounded",
              "max-w-sm whitespace-normal break-words",
              "data-[state=delayed-open]:animate-in data-[state=closed]:animate-out",
              "data-[state=delayed-open]:fade-in-0 data-[state=closed]:fade-out-0",
            )}
          >
            {tooltipText}
          </RTooltip.Content>
        </RTooltip.Portal>
      </RTooltip.Root>
    </RTooltip.Provider>
  )
}
