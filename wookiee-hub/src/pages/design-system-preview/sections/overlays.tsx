import { useState } from "react"
import {
  Command,
  Copy,
  Download,
  Edit3,
  ExternalLink,
  Filter,
  MoreHorizontal,
  Trash2,
} from "lucide-react"
import {
  Button,
  Checkbox,
  IconButton,
  Kbd,
} from "@/components/ui-v2/primitives"
import {
  CommandPalette,
  ContextMenu,
  Drawer,
  DropdownMenu,
  Modal,
  Popover,
} from "@/components/ui-v2/overlays"
import {
  DatePicker,
  MultiSelectField,
  SelectField,
  TextField,
} from "@/components/ui-v2/forms"
import { useToast } from "@/components/ui-v2/feedback"
import { Demo, SubSection } from "../shared"

/**
 * OverlaysSection — canonical reference: `foundation.jsx:2372-2461`.
 *
 * Each canonical Demo card is preserved with the same controls (modal, two
 * drawers — right + bottom, popover, dropdown, context menu, command
 * palette). We additionally surface the `filters` / `detail` size aliases
 * for Drawer per the canonical patterns.jsx pattern.
 */
const SIZE_OPTIONS = [
  { value: "XS", label: "XS" },
  { value: "S", label: "S" },
  { value: "M", label: "M" },
  { value: "L", label: "L" },
  { value: "XL", label: "XL" },
]

const CATEGORY_OPTIONS = [
  { id: "1", nazvanie: "Бюстгальтер" },
  { id: "2", nazvanie: "Трусы" },
  { id: "3", nazvanie: "Комплект" },
]

export function OverlaysSection() {
  const [modal, setModal] = useState(false)
  const [drawerFilters, setDrawerFilters] = useState(false)
  const [drawerDetail, setDrawerDetail] = useState(false)
  const [drawerBottom, setDrawerBottom] = useState(false)
  const [palette, setPalette] = useState(false)

  const [filterSizes, setFilterSizes] = useState<string[]>(["S", "M"])
  const [filterCategory, setFilterCategory] = useState("1")
  const [bulkComment, setBulkComment] = useState("")

  const toast = useToast()

  return (
    <div className="space-y-12">
      {/* === Modal === */}
      <SubSection title="Modal" columns={2}>
        <Demo title="Открыть модалку">
          <Button onClick={() => setModal(true)}>Удалить модель</Button>
          <Modal
            open={modal}
            onClose={() => setModal(false)}
            title="Удаление модели"
            footer={
              <>
                <Button variant="secondary" onClick={() => setModal(false)}>
                  Отмена
                </Button>
                <Button variant="danger" onClick={() => setModal(false)}>
                  Удалить
                </Button>
              </>
            }
          >
            <div className="text-sm text-secondary">
              Модель <span className="font-mono text-xs">Vuki</span> и все её 24
              артикула будут перемещены в архив. Это действие можно отменить в
              течение 7 дней.
            </div>
          </Modal>
        </Demo>

        <Demo title="CommandPalette (⌘K)">
          <Button variant="secondary" icon={Command} onClick={() => setPalette(true)}>
            Открыть поиск
          </Button>
          <span className="text-xs text-muted ml-2">
            <Kbd>⌘</Kbd> <Kbd>K</Kbd>
          </span>
          <CommandPalette
            open={palette}
            onClose={() => setPalette(false)}
            commands={[
              {
                id: "vuki",
                label: "Vuki — основа коллекции",
                description: "Бюстгальтер · 24 артикула",
                itemType: "МОДЕЛЬ",
                onSelect: () => toast.toast("Vuki"),
              },
              {
                id: "vivi",
                label: "Vivi — Push-up",
                description: "Бюстгальтер · 18 артикулов",
                itemType: "МОДЕЛЬ",
                onSelect: () => toast.toast("Vivi"),
              },
              {
                id: "black",
                label: "Чёрный",
                description: "#1C1917 · 142 SKU",
                itemType: "ЦВЕТ",
                onSelect: () => toast.toast("Чёрный"),
              },
              {
                id: "sales",
                label: "Аналитика → Продажи",
                description: "/analytics/sales",
                itemType: "СТРАНИЦА",
                shortcut: "G S",
                onSelect: () => toast.toast("Sales"),
              },
            ]}
          />
        </Demo>
      </SubSection>

      {/* === Drawer / Sheet === */}
      <SubSection title="Drawer / Sheet" columns={2}>
        <Demo title="Drawer filters (420px) — справа">
          <Button variant="secondary" onClick={() => setDrawerFilters(true)}>
            Открыть фильтры
          </Button>
          <Drawer
            open={drawerFilters}
            onClose={() => setDrawerFilters(false)}
            title="Фильтры"
            size="filters"
            side="right"
            footer={
              <>
                <Button variant="ghost" size="sm">
                  Сбросить
                </Button>
                <Button size="sm" onClick={() => setDrawerFilters(false)}>
                  Применить
                </Button>
              </>
            }
          >
            <div className="space-y-4">
              <SelectField
                id="dr-cat"
                label="Категория"
                value={filterCategory}
                onChange={setFilterCategory}
                options={CATEGORY_OPTIONS}
              />
              <MultiSelectField
                id="dr-sizes"
                label="Размеры"
                value={filterSizes}
                onChange={setFilterSizes}
                options={SIZE_OPTIONS}
              />
              <DatePicker id="dr-range" label="Период" range value={null} onChange={() => null} />
            </div>
          </Drawer>
        </Demo>

        <Demo title="Drawer detail (560px) — справа">
          <Button variant="secondary" onClick={() => setDrawerDetail(true)}>
            Открыть detail
          </Button>
          <Drawer
            open={drawerDetail}
            onClose={() => setDrawerDetail(false)}
            title="Детали карточки"
            description="size='detail' — 560px, паттерн Kanban detail-drawer."
            size="detail"
            side="right"
          >
            <div className="text-sm text-secondary">
              Использование: правка карточки Канбана, интеграции, конфигурация
              ботов. Размер 560 — оптимум для двухколоночного layout'а внутри.
            </div>
          </Drawer>
        </Demo>

        <Demo title="Bottom sheet (60vh)">
          <Button variant="secondary" onClick={() => setDrawerBottom(true)}>
            Открыть снизу
          </Button>
          <Drawer
            open={drawerBottom}
            onClose={() => setDrawerBottom(false)}
            title="Bulk-редактирование"
            side="bottom"
            size="md"
          >
            <div className="space-y-4">
              <SelectField
                id="dr-bulk-status"
                label="Изменить статус для 12 SKU"
                value="1"
                onChange={() => null}
                options={[
                  { id: "1", nazvanie: "В продаже" },
                  { id: "2", nazvanie: "Запуск" },
                  { id: "5", nazvanie: "Архив" },
                ]}
              />
              <TextField
                id="dr-bulk-comment"
                label="Комментарий"
                value={bulkComment}
                onChange={setBulkComment}
              />
            </div>
          </Drawer>
        </Demo>
      </SubSection>

      {/* === Popover, Dropdown, Context menu === */}
      <SubSection title="Popover, Dropdown, Context menu" columns={3}>
        <Demo title="Popover">
          <Popover
            trigger={
              <Button variant="secondary" icon={Filter}>
                Фильтр
              </Button>
            }
            placement="bottom-start"
          >
            <div className="bg-elevated border border-default rounded-lg p-3 shadow-md w-56 space-y-2">
              <Checkbox id="pp-1" checked onChange={() => null} label="В продаже" />
              <Checkbox id="pp-2" checked={false} onChange={() => null} label="Запуск" />
              <Checkbox id="pp-3" checked={false} onChange={() => null} label="Архив" />
            </div>
          </Popover>
        </Demo>

        <Demo title="Dropdown menu">
          <DropdownMenu
            trigger={
              <IconButton aria-label="Дополнительно" icon={MoreHorizontal} variant="secondary" />
            }
            items={[
              {
                label: "Редактировать",
                icon: Edit3,
                shortcut: "E",
                onClick: () => toast.toast("Edit"),
              },
              { label: "Дублировать", icon: Copy, onClick: () => toast.toast("Duplicated") },
              { label: "Экспорт", icon: Download, onClick: () => toast.toast("Export") },
              { divider: true, label: "" },
              {
                label: "Удалить",
                icon: Trash2,
                danger: true,
                shortcut: "D",
                onClick: () => toast.toast("Deleted", { variant: "danger" }),
              },
            ]}
          />
        </Demo>

        <Demo title="Context menu (right-click)">
          <ContextMenu
            items={[
              { label: "Открыть", icon: ExternalLink, onClick: () => toast.toast("Open") },
              { label: "Скопировать ссылку", icon: Copy, onClick: () => toast.toast("Copied") },
              { divider: true, label: "" },
              {
                label: "Удалить",
                icon: Trash2,
                danger: true,
                onClick: () => toast.toast("Deleted", { variant: "danger" }),
              },
            ]}
          >
            <div className="px-4 py-3 rounded-md text-sm cursor-pointer bg-surface-muted text-secondary border border-default">
              Кликни правой кнопкой ↗
            </div>
          </ContextMenu>
        </Demo>
      </SubSection>
    </div>
  )
}
