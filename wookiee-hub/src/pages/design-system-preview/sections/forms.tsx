import { useState } from "react"
import {
  ColorPicker,
  Combobox,
  DatePicker,
  FieldWrap,
  FileUpload,
  MultiSelectField,
  NumberField,
  SelectField,
  TextField,
  TextareaField,
  TimePicker,
} from "@/components/ui-v2/forms"
import type { DateRange } from "@/components/ui-v2/forms"
import { Demo, SubSection } from "../shared"

/**
 * FormsSection — canonical reference: `foundation.jsx:1116-1181`.
 *
 * Every block stays controlled — local useState mirrors the canonical
 * function-component state at line 1117-1127. Each form field renders
 * inside its own `FieldWrap` so the label + hint layout is consistent.
 */
const CATEGORY_OPTIONS = [
  { id: "1", nazvanie: "Бюстгальтер" },
  { id: "2", nazvanie: "Трусы" },
  { id: "3", nazvanie: "Комплект" },
]

const SIZE_OPTIONS = [
  { value: "XS", label: "XS" },
  { value: "S", label: "S" },
  { value: "M", label: "M" },
  { value: "L", label: "L" },
  { value: "XL", label: "XL" },
]

const MODEL_OPTIONS = [
  { value: "vuki", label: "Vuki" },
  { value: "vivi", label: "Vivi" },
  { value: "vesta", label: "Vesta" },
  { value: "vera", label: "Vera" },
  { value: "vita", label: "Vita" },
  { value: "volna", label: "Volna" },
]

export function FormsSection() {
  const [text, setText] = useState("Vuki")
  const [num, setNum] = useState<number | null>(2890)
  const [sel, setSel] = useState("1")
  const [multi, setMulti] = useState<string[]>(["S", "M"])
  const [textarea, setTextarea] = useState("")
  const [date, setDate] = useState<Date | null>(new Date(2026, 4, 10))
  const [range, setRange] = useState<DateRange | null>({
    from: new Date(2026, 4, 5),
    to: new Date(2026, 4, 15),
  })
  const [time, setTime] = useState<string | null>("10:30")
  const [comboInput, setComboInput] = useState<string | null>("vuki")
  const [comboBtn, setComboBtn] = useState<string | null>("vivi")
  const [color, setColor] = useState("#7C3AED")
  const [files, setFiles] = useState<File[] | null>(null)

  return (
    <div className="space-y-12">
      {/* === Базовые поля формы === */}
      <SubSection
        title="Базовые поля формы"
        description="С обёрткой FieldWrap — лейбл UPPERCASE + LevelBadge (M/V/A/S) + опциональный hint."
        columns={2}
      >
        <Demo title="TextField">
          <div className="w-full">
            <TextField
              id="f-text"
              label="Название модели"
              level="model"
              value={text}
              onChange={setText}
              hint="Уникальное в рамках бренда"
            />
          </div>
        </Demo>

        <Demo title="NumberField с suffix">
          <div className="w-full">
            <NumberField
              id="f-num"
              label="Цена розничная"
              level="sku"
              value={num}
              onChange={setNum}
              suffix={<span className="text-muted text-xs">₽</span>}
            />
          </div>
        </Demo>

        <Demo title="SelectField">
          <div className="w-full">
            <SelectField
              id="f-sel"
              label="Категория"
              level="model"
              value={sel}
              onChange={setSel}
              options={CATEGORY_OPTIONS}
            />
          </div>
        </Demo>

        <Demo title="MultiSelectField (chips-toggle)">
          <div className="w-full">
            <MultiSelectField
              id="f-multi"
              label="Размерная линейка"
              level="artikul"
              value={multi}
              onChange={setMulti}
              options={SIZE_OPTIONS}
              hint="DS §6 — chips-toggles inline, не dropdown."
            />
          </div>
        </Demo>

        <Demo title="TextareaField">
          <div className="w-full">
            <TextareaField
              id="f-area"
              label="Описание"
              value={textarea}
              onChange={setTextarea}
              maxLength={200}
              autoResize
            />
          </div>
        </Demo>

        <Demo title="Mono TextField">
          <div className="w-full">
            <TextField
              id="f-mono"
              label="Артикул WB"
              level="sku"
              mono
              value="WB-12847562"
              onChange={() => null}
            />
          </div>
        </Demo>

        <Demo title="С ошибкой">
          <div className="w-full">
            <FieldWrap id="f-err" label="Обязательное" error="Поле не может быть пустым">
              <TextField
                id="f-err-inner"
                value=""
                onChange={() => null}
                error="Поле не может быть пустым"
              />
            </FieldWrap>
          </div>
        </Demo>
      </SubSection>

      {/* === Расширенные поля === */}
      <SubSection
        title="Расширенные поля"
        description="DatePicker single+range, TimePicker, Combobox input+button, ColorPicker, FileUpload."
        columns={2}
      >
        <Demo title="DatePicker (single)">
          <div className="w-full">
            <DatePicker id="f-date" label="Дата запуска" value={date} onChange={setDate} />
          </div>
        </Demo>

        <Demo title="DatePicker (range)">
          <div className="w-full">
            <DatePicker
              id="f-range"
              label="Период промо"
              range
              value={range}
              onChange={setRange}
              hint="Два клика: from → to (с автоматическим swap)"
            />
          </div>
        </Demo>

        <Demo title="TimePicker">
          <div className="w-full">
            <TimePicker
              id="f-time"
              label="Время съёмки"
              value={time}
              onChange={setTime}
              hint="30-мин шаг, 08:00 — 21:00"
            />
          </div>
        </Demo>

        <Demo title="Combobox (input mode)">
          <div className="w-full">
            <Combobox
              id="f-combo-in"
              label="Модель"
              value={comboInput}
              onChange={setComboInput}
              options={MODEL_OPTIONS}
            />
          </div>
        </Demo>

        <Demo title="Combobox (button mode)">
          <div className="w-full">
            <Combobox
              id="f-combo-btn"
              label="Модель"
              mode="button"
              value={comboBtn}
              onChange={setComboBtn}
              options={MODEL_OPTIONS}
              hint="Closed-state = trigger button; внутри popover — поиск + listbox."
            />
          </div>
        </Demo>

        <Demo title="ColorPicker">
          <div className="w-full">
            <ColorPicker
              id="f-color"
              label="Цвет товара"
              value={color}
              onChange={setColor}
              hint="9-цветная палитра + произвольный hex"
            />
          </div>
        </Demo>

        <Demo title="FileUpload" full>
          <div className="w-full">
            <FileUpload
              id="f-file"
              label="Технические документы"
              value={files}
              onChange={setFiles}
              multiple
              maxSize={5 * 1024 * 1024}
              description="PNG, JPG, PDF — до 5 МБ"
            />
          </div>
        </Demo>
      </SubSection>
    </div>
  )
}
