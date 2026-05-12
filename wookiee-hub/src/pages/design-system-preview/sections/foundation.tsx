import { Demo, SubLabel, SubSection } from "../shared"

/**
 * FoundationSection — palette, semantic tokens, typography, spacing.
 *
 * Canonical reference: `foundation.jsx:785-916` (`function Foundation()`).
 *
 * Notes on raw `bg-stone-*` usage in this file:
 *   The palette swatches are *demo content* — we are literally displaying
 *   the underlying stone scale, so the raw classes ARE the data. Same goes
 *   for the spacing scale visualiser. This is the canonical escape hatch
 *   per the DS audit: «raw Tailwind colors are allowed when the demo IS
 *   the color».
 */
const STONE_SCALE = [
  { c: "50", hex: "#FAFAF9", bg: "bg-stone-50" },
  { c: "100", hex: "#F5F5F4", bg: "bg-stone-100" },
  { c: "200", hex: "#E7E5E4", bg: "bg-stone-200" },
  { c: "300", hex: "#D6D3D1", bg: "bg-stone-300" },
  { c: "400", hex: "#A8A29E", bg: "bg-stone-400" },
  { c: "500", hex: "#78716C", bg: "bg-stone-500" },
  { c: "600", hex: "#57534E", bg: "bg-stone-600" },
  { c: "700", hex: "#44403C", bg: "bg-stone-700" },
  { c: "800", hex: "#292524", bg: "bg-stone-800" },
  { c: "900", hex: "#1C1917", bg: "bg-stone-900" },
  { c: "950", hex: "#0C0A09", bg: "bg-stone-950" },
] as const

const SEMANTIC_PALETTE = [
  { name: "Emerald", hex: "#059669", use: "success / в продаже" },
  { name: "Blue", hex: "#2563EB", use: "info / запуск" },
  { name: "Amber", hex: "#D97706", use: "warning / выводим" },
  { name: "Rose", hex: "#E11D48", use: "danger / не выводится" },
  { name: "Purple", hex: "#7C3AED", use: "brand accent (логотип, активный nav)" },
] as const

const TOKEN_ROWS = [
  { tk: "surface", light: "white", dark: "stone-900", use: "фон карточек" },
  { tk: "page", light: "stone-50/40", dark: "stone-950", use: "фон страницы" },
  { tk: "surface-muted", light: "stone-50/60", dark: "stone-900/40", use: "sidebar, hover" },
  { tk: "elevated", light: "white", dark: "stone-900", use: "поднятые карточки, toast" },
  { tk: "text-primary", light: "stone-900", dark: "stone-50", use: "основной текст" },
  { tk: "text-secondary", light: "stone-700", dark: "stone-300", use: "вторичный текст" },
  { tk: "text-muted", light: "stone-500", dark: "stone-400", use: "подписи" },
  { tk: "text-label", light: "stone-400", dark: "stone-500", use: "лейблы UPPERCASE" },
  { tk: "border-default", light: "stone-200", dark: "stone-800", use: "обводки карточек" },
  { tk: "border-strong", light: "stone-300", dark: "stone-700", use: "усиленные обводки" },
] as const

const SPACING_SCALE = [
  { tk: "gap-1.5", px: 6 },
  { tk: "gap-2", px: 8 },
  { tk: "gap-3", px: 12 },
  { tk: "gap-4", px: 16 },
  { tk: "gap-6", px: 24 },
  { tk: "gap-8", px: 32 },
] as const

export function FoundationSection() {
  return (
    <div className="space-y-12">
      <SubSection
        title="Цветовая палитра"
        description="Базовая — Tailwind stone. Никаких gray/slate/zinc/neutral в JSX."
      >
        <Demo title="Stone scale" note="bg-stone-{50..950}" full>
          <div className="grid grid-cols-11 gap-1.5 w-full">
            {STONE_SCALE.map((s) => (
              <div key={s.c} className="text-center">
                <div
                  className={`w-full aspect-square rounded ring-1 ring-stone-200 dark:ring-stone-700 mb-1 ${s.bg}`}
                />
                <div className="text-[10px] tabular-nums text-secondary">{s.c}</div>
                <div className="text-[9px] font-mono text-label">{s.hex}</div>
              </div>
            ))}
          </div>
        </Demo>

        <Demo title="Семантические цвета" note="<Badge variant=...>" full>
          <div className="grid grid-cols-5 gap-3 w-full">
            {SEMANTIC_PALETTE.map((s) => (
              <div key={s.name} className="p-3 rounded-md bg-surface-muted">
                <div
                  className="w-full h-12 rounded mb-2"
                  style={{ background: s.hex }}
                />
                <div className="text-xs font-medium text-primary">{s.name}</div>
                <div className="text-[10px] font-mono text-label">{s.hex}</div>
                <div className="text-[10px] mt-1 text-muted">{s.use}</div>
              </div>
            ))}
          </div>
        </Demo>
      </SubSection>

      <SubSection
        title="Семантические токены"
        description="Все компоненты ходят через CSS-переменные (см. tokens.css). Никаких inline stone-* в продакшен-JSX."
      >
        <Demo title="Surface, text, border" full>
          <div className="w-full rounded-lg border border-default overflow-hidden">
            <table className="w-full text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-muted bg-surface-muted">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Токен</th>
                  <th className="px-3 py-2 text-left font-medium">Light</th>
                  <th className="px-3 py-2 text-left font-medium">Dark</th>
                  <th className="px-3 py-2 text-left font-medium">Применение</th>
                </tr>
              </thead>
              <tbody>
                {TOKEN_ROWS.map((row) => (
                  <tr key={row.tk} className="border-t border-default">
                    <td className="px-3 py-2">
                      <code className="font-mono text-xs text-primary">{row.tk}</code>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-secondary">{row.light}</td>
                    <td className="px-3 py-2 font-mono text-xs text-secondary">{row.dark}</td>
                    <td className="px-3 py-2 text-xs text-muted">{row.use}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Demo>
      </SubSection>

      <SubSection
        title="Типографика"
        description="DM Sans (UI) + Instrument Serif (заголовки страниц, italic для бренда)."
      >
        <Demo title="Шрифты" full>
          <div className="space-y-4 w-full">
            <div>
              <SubLabel>Page title — Instrument Serif italic 4xl</SubLabel>
              <div className="font-serif italic text-4xl text-primary leading-tight">
                Wookiee Hub · Каталог
              </div>
            </div>
            <div>
              <SubLabel>Section title — DM Sans 500 / 2xl</SubLabel>
              <div className="text-2xl font-medium text-primary">Атрибуты модели</div>
            </div>
            <div>
              <SubLabel>Card section title — DM Sans 500 / base</SubLabel>
              <div className="text-base font-medium text-primary">Контент</div>
            </div>
            <div>
              <SubLabel>Body — DM Sans 400 / 14px</SubLabel>
              <div className="text-sm text-primary">
                Линейка размеров: S — M — L — XL. Базовая модель Vuki — основа коллекции
                Lite, продаётся через WB и Ozon.
              </div>
            </div>
            <div>
              <SubLabel>Label uppercase — DM Sans 500 / 11px tracking-wider</SubLabel>
              <div className="text-[11px] uppercase tracking-wider text-muted">
                СТАТУС МОДЕЛИ
              </div>
            </div>
            <div>
              <SubLabel>Numbers — tabular-nums 2xl</SubLabel>
              <div className="text-2xl tabular-nums text-primary">1 248,00 ₽</div>
            </div>
            <div>
              <SubLabel>Mono — font-mono / xs (артикулы, штрих-коды, ID)</SubLabel>
              <div className="text-xs font-mono text-secondary">
                VUK-BLK-S · 4607177384962 · gjvwcdtfg
              </div>
            </div>
          </div>
        </Demo>
      </SubSection>

      <SubSection title="Spacing" description="База — 4px. Основной набор отступов 6 → 32 px.">
        <Demo title="Scale" full>
          <div className="space-y-2 w-full">
            {SPACING_SCALE.map((s) => (
              <div key={s.tk} className="flex items-center gap-3">
                <code className="font-mono text-xs w-20 text-secondary">{s.tk}</code>
                <div
                  className="bg-stone-900 dark:bg-stone-50"
                  style={{ width: s.px, height: 8 }}
                />
                <span className="text-xs tabular-nums text-muted">{s.px}px</span>
              </div>
            ))}
          </div>
        </Demo>
      </SubSection>
    </div>
  )
}
