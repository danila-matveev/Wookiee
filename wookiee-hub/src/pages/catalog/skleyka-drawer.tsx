// W10.26 — SkleykaDrawer.
//
// Тонкая обёртка вокруг существующего `SkleykaCard` (см. skleyka-card.tsx),
// чтобы открывать склейку в виде right-side drawer'а поверх реестров /artikuly
// и /tovary — по аналогии с ArtikulDrawer / SkuDrawer.
//
// Сам SkleykaCard не модифицируется: компонент уже умеет рендериться как
// flex-1 column.  Здесь мы добавляем fixed-position контейнер + backdrop + Esc.

import { useEffect } from "react"
import { SkleykaCard } from "./skleyka-card"

interface SkleykaDrawerProps {
  /** id склейки в `skleyki_wb` или `skleyki_ozon`. */
  skleykaId: number
  /** Канал — определяет таблицу справочника и junction. */
  channel: "wb" | "ozon"
  /** Закрыть drawer (например, очистить state на родительской странице). */
  onClose: () => void
}

export function SkleykaDrawer({ skleykaId, channel, onClose }: SkleykaDrawerProps) {
  // Esc → закрыть.  ArtikulDrawer / SkuDrawer делают то же самое, чтобы
  // единый UX-паттерн.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  return (
    <>
      {/* backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* drawer — широкий (склейка содержит таблицу SKU + sidebar) */}
      <div
        className="fixed inset-y-0 right-0 w-[min(1180px,98vw)] bg-stone-50 rounded-l-2xl shadow-2xl z-50 overflow-hidden flex flex-col"
        role="dialog"
        aria-label="Карточка склейки"
      >
        <SkleykaCard id={skleykaId} channel={channel} onBack={onClose} />
      </div>
    </>
  )
}
