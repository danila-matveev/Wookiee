import { useState } from "react"
import { Archive, Copy, Tag } from "lucide-react"
import {
  BulkActionsBar,
  ColorSwatch,
  ColumnsManager,
  type ColumnDef,
  CommandPalette,
  type CommandResult,
  type SearchGlobalResult,
  CompletenessRing,
  FieldWrap,
  LevelBadge,
  MultiSelectField,
  NumberField,
  RefModal,
  type RefFieldDef,
  SelectField,
  StatusBadge,
  StatusDot,
  StringSelectField,
  TextField,
  TextareaField,
  Tooltip,
} from "./index"

const SAMPLE_COLUMNS: ColumnDef[] = [
  { key: "artikul", label: "Артикул", default: true },
  { key: "model", label: "Модель", default: true },
  { key: "cvet", label: "Цвет", default: true },
  { key: "wb_nom", label: "WB номенклатура", default: true, badge: "канал" },
  { key: "ozon_art", label: "OZON артикул", default: false, badge: "канал" },
  { key: "kollekciya", label: "Коллекция", default: false },
  { key: "fabrika", label: "Фабрика", default: false },
]

const REF_FIELDS: RefFieldDef[] = [
  { key: "nazvanie", label: "Название", type: "text", required: true },
  { key: "opisanie", label: "Описание", type: "textarea" },
  {
    key: "tip",
    label: "Тип",
    type: "select",
    options: [
      { value: "pack", label: "Пакет" },
      { value: "cosmetic", label: "Косметичка" },
      { value: "tag", label: "Бирка" },
    ],
  },
  { key: "price_yuan", label: "Цена (¥)", type: "number" },
  { key: "active", label: "Активен", type: "checkbox" },
  { key: "file_link", label: "Ссылка на файл", type: "file_url", placeholder: "https://drive.google.com/…" },
]

const MOCK_SEARCH = async (q: string): Promise<SearchGlobalResult> => {
  const ql = q.toLowerCase()
  const models: CommandResult[] = [
    { id: 1, category: "Модели" as const, label: "Vuki", sub: "Комплект белья · Базовый трикотаж" },
    { id: 2, category: "Модели" as const, label: "Moon", sub: "Комплект Moon Jelly" },
    { id: 3, category: "Модели" as const, label: "Ruby", sub: "Бра Ruby Audrey" },
  ].filter((m) => m.label.toLowerCase().includes(ql) || m.sub?.toLowerCase().includes(ql))
  const colors: CommandResult[] = [
    { id: 1, category: "Цвета" as const, label: "2", sub: "чёрный · tricot", hex: "#1C1917" },
    { id: 2, category: "Цвета" as const, label: "1", sub: "белый · tricot", hex: "#FAFAF9" },
    { id: 3, category: "Цвета" as const, label: "AU001", sub: "пыльная роза · audrey", hex: "#C9A0A0" },
  ].filter((c) => c.label.toLowerCase().includes(ql) || c.sub?.toLowerCase().includes(ql))
  const articles: CommandResult[] = [
    { id: 1, category: "Артикулы" as const, label: "компбел-ж-бесшов/2", sub: "Vuki · чёрный" },
    { id: 2, category: "Артикулы" as const, label: "компбел-ж-jelly/w7", sub: "Moon · пастельно-розовый" },
  ].filter((a) => a.label.toLowerCase().includes(ql) || a.sub?.toLowerCase().includes(ql))
  const skus: CommandResult[] = [
    { id: 1, category: "SKU" as const, label: "4602000001234", sub: "Vuki · чёрный · M" },
    { id: 2, category: "SKU" as const, label: "4602000005678", sub: "Moon · pale pink · L" },
  ].filter((s) => s.label.includes(ql))
  return { models, colors, articles, skus }
}

/**
 * Catalog UI demo — renders all atomic components for visual review.
 * Wrap with .catalog-scope to apply the stone-light theme.
 */
export function CatalogUiDemo() {
  const [refOpen, setRefOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [text, setText] = useState("Vuki Black Edition")
  const [num, setNum] = useState<number>(0.18)
  const [sel, setSel] = useState<number | string>(2)
  const [strSel, setStrSel] = useState("Бесшовное белье Jelly")
  const [multi, setMulti] = useState<string[]>(["S", "M", "L"])
  const [textarea, setTextarea] = useState("Базовый бесшовный комплект из мягкого трикотажа.")
  const [columns, setColumns] = useState<string[]>(
    SAMPLE_COLUMNS.filter((c) => c.default).map((c) => c.key),
  )
  const [selected, setSelected] = useState<number[]>([])

  return (
    <div className="catalog-scope min-h-screen bg-stone-50/40 text-stone-900 antialiased">
      <style>{`@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap');`}</style>
      <div className="max-w-5xl mx-auto px-6 py-10 space-y-12">
        <header>
          <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">Demo</div>
          <h1
            className="cat-font-serif text-4xl text-stone-900 italic"
            style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif" }}
          >
            Catalog UI components
          </h1>
          <p className="text-sm text-stone-500 mt-2">
            Wave 1 · A3 — atomic UI компоненты каталога Wookiee Hub.
          </p>
        </header>

        <Section title="Tooltip">
          <div className="flex gap-6 items-center">
            <Tooltip text="Top tooltip"><Btn>top</Btn></Tooltip>
            <Tooltip text="Bottom tooltip" position="bottom"><Btn>bottom</Btn></Tooltip>
            <Tooltip text="Left" position="left"><Btn>left</Btn></Tooltip>
            <Tooltip text="Right" position="right"><Btn>right</Btn></Tooltip>
          </div>
        </Section>

        <Section title="LevelBadge">
          <div className="flex gap-2 items-center">
            <LevelBadge level="model" />
            <LevelBadge level="variation" />
            <LevelBadge level="artikul" />
            <LevelBadge level="sku" />
          </div>
        </Section>

        <Section title="StatusBadge & StatusDot">
          <div className="flex flex-wrap gap-2 items-center">
            <StatusBadge status={{ nazvanie: "В продаже", color: "green" }} />
            <StatusBadge status={{ nazvanie: "Запуск", color: "blue" }} />
            <StatusBadge status={{ nazvanie: "Архив", color: "gray" }} />
            <StatusBadge status={{ nazvanie: "Разработка", color: "amber" }} />
            <StatusBadge status={{ nazvanie: "Выводим", color: "red" }} />
            <StatusBadge statusId={6} />
            <StatusBadge statusId={7} compact />
            <span className="ml-4 inline-flex items-center gap-1 text-xs text-stone-500">
              dots: <StatusDot color="green" /><StatusDot color="blue" /><StatusDot color="amber" /><StatusDot color="red" /><StatusDot color="gray" />
            </span>
          </div>
        </Section>

        <Section title="CompletenessRing — пороги цветов">
          <div className="flex gap-6 items-center">
            <CompletenessRing value={0.15} />
            <CompletenessRing value={0.5} />
            <CompletenessRing value={0.78} />
            <CompletenessRing value={0.95} />
            <CompletenessRing value={0.93} size={42} />
            <CompletenessRing value={0.45} size={16} hideLabel />
          </div>
        </Section>

        <Section title="ColorSwatch">
          <div className="flex gap-2 items-center">
            <ColorSwatch hex="#1C1917" />
            <ColorSwatch hex="#9B2335" size={24} />
            <ColorSwatch hex="#C9A0A0" size={32} />
            <ColorSwatch hex="#C9B6E4" size={48} />
          </div>
        </Section>

        <Section title="Fields — readonly mode">
          <div className="grid grid-cols-2 gap-4 max-w-3xl">
            <TextField label="Код" value="Vuki" level="model" readonly />
            <NumberField label="Вес" value={0.18} suffix="кг" level="model" readonly />
            <SelectField
              label="Категория"
              value={1}
              options={[{ id: 1, nazvanie: "Комплект белья" }, { id: 2, nazvanie: "Трусы" }]}
              level="model"
              readonly
            />
            <StringSelectField
              label="Тип коллекции"
              value="Бесшовное белье Jelly"
              options={["Трикотажное белье", "Бесшовное белье Jelly", "Бесшовное белье Audrey"]}
              level="model"
              readonly
            />
            <MultiSelectField
              label="Размеры"
              value={["XS", "S", "M", "L", "XL"]}
              options={["XS", "S", "M", "L", "XL", "XXL"]}
              level="model"
              readonly
            />
            <TextareaField
              label="Описание"
              value="Базовый бесшовный комплект из мягкого трикотажа."
              level="model"
              readonly
            />
          </div>
        </Section>

        <Section title="Fields — edit mode">
          <div className="grid grid-cols-2 gap-4 max-w-3xl">
            <TextField label="Код" value={text} onChange={setText} level="variation" />
            <NumberField label="Вес" value={num} onChange={setNum} suffix="кг" level="model" />
            <SelectField
              label="Статус"
              value={sel}
              onChange={setSel}
              options={[
                { id: 1, nazvanie: "В продаже" },
                { id: 2, nazvanie: "Запуск" },
                { id: 3, nazvanie: "Архив" },
              ]}
              level="model"
            />
            <StringSelectField
              label="Тип коллекции"
              value={strSel}
              onChange={setStrSel}
              options={["Трикотажное белье", "Бесшовное белье Jelly", "Бесшовное белье Audrey"]}
              level="model"
            />
            <MultiSelectField
              label="Размеры"
              value={multi}
              onChange={setMulti}
              options={["XS", "S", "M", "L", "XL", "XXL"]}
              level="model"
            />
            <TextareaField label="Описание" value={textarea} onChange={setTextarea} level="model" />
          </div>
        </Section>

        <Section title="FieldWrap — ручная композиция">
          <div className="grid grid-cols-2 gap-4 max-w-3xl">
            <FieldWrap label="Любое поле" level="artikul" hint="LevelBadge показывает уровень">
              <div className="px-2.5 py-1.5 text-sm font-mono text-stone-900 border border-stone-200 rounded-md bg-white">
                компбел-ж-бесшов/2
              </div>
            </FieldWrap>
          </div>
        </Section>

        <Section title="ColumnsManager">
          <div className="flex items-start gap-6 flex-wrap">
            <ColumnsManager
              columns={SAMPLE_COLUMNS}
              value={columns}
              onChange={setColumns}
              scope="demo-table"
              storageKey="visible-columns"
            />
            <div className="text-xs text-stone-500">
              <div className="mb-1 uppercase tracking-wider text-[10px] text-stone-400">
                Активные ({columns.length})
              </div>
              <ol className="list-decimal list-inside space-y-0.5">
                {columns.map((k) => (
                  <li key={k} className="font-mono text-stone-700">{k}</li>
                ))}
              </ol>
            </div>
          </div>
        </Section>

        <Section title="RefModal & CommandPalette">
          <div className="flex gap-2 flex-wrap">
            <Btn onClick={() => setRefOpen(true)}>Открыть RefModal</Btn>
            <Btn onClick={() => setPaletteOpen(true)}>Открыть CommandPalette</Btn>
            <Btn onClick={() => setSelected([1, 2, 3])}>Выбрать 3 строки (BulkActionsBar)</Btn>
          </div>
          {refOpen && (
            <RefModal
              title="Новая упаковка"
              fields={REF_FIELDS}
              initial={{ tip: "pack", active: true }}
              onCancel={() => setRefOpen(false)}
              onSave={async (vals) => {
                console.info("[RefModal save]", vals)
                setRefOpen(false)
              }}
            />
          )}
          <CommandPalette
            open={paletteOpen}
            onClose={() => setPaletteOpen(false)}
            searchFn={MOCK_SEARCH}
            onPick={(r) => console.info("[CommandPalette pick]", r)}
          />
        </Section>
      </div>

      <BulkActionsBar
        position="fixed-bottom"
        selectedCount={selected.length}
        onClear={() => setSelected([])}
        actions={[
          { id: "status", label: "Изменить статус", icon: <Tag className="w-3 h-3" />, onClick: () => alert("status") },
          { id: "duplicate", label: "Дублировать", icon: <Copy className="w-3 h-3" />, onClick: () => alert("dup") },
          { id: "archive", label: "В архив", icon: <Archive className="w-3 h-3" />, onClick: () => alert("arch"), destructive: true },
        ]}
      />
    </div>
  )
}

interface SectionProps {
  title: string
  children: React.ReactNode
}

function Section({ title, children }: SectionProps) {
  return (
    <section>
      <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-3 font-medium">
        {title}
      </div>
      <div className="bg-white border border-stone-200 rounded-lg p-5">{children}</div>
    </section>
  )
}

function Btn({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-3 py-1.5 text-sm text-stone-700 bg-white border border-stone-200 hover:bg-stone-100 rounded-md"
    >
      {children}
    </button>
  )
}

export default CatalogUiDemo
