import { useState } from "react"
import {
  Bell,
  Download,
  Edit3,
  HelpCircle,
  Info,
  Plus,
  Search,
  Settings,
  Trash2,
  AlertTriangle,
  Hash,
} from "lucide-react"
import {
  Avatar,
  AvatarGroup,
  Badge,
  Button,
  Checkbox,
  Chip,
  ColorSwatch,
  FilterChip,
  IconButton,
  Kbd,
  LevelBadge,
  PermissionGate,
  PriorityBadge,
  ProgressBar,
  Radio,
  Ring,
  Skeleton,
  Slider,
  StatusBadge,
  Tag,
  Toggle,
  Tooltip,
} from "@/components/ui-v2/primitives"
import { TextField } from "@/components/ui-v2/forms"
import { Demo, SubSection } from "../shared"

/**
 * AtomsSection — canonical reference: `foundation.jsx:922-1110`.
 *
 * Every block here mirrors the matching `Demo` in that section. Interactive
 * states (Checkbox/Radio/Toggle/Slider) live in local useState — same as
 * canonical lines 923-927.
 */
export function AtomsSection() {
  const [check1, setCheck1] = useState(true)
  const [check2, setCheck2] = useState(false)
  const [radioValue, setRadioValue] = useState("a")
  const [toggleA, setToggleA] = useState(true)
  const [sliderValue, setSliderValue] = useState(45)
  const [filterA, setFilterA] = useState(true)
  const [filterB, setFilterB] = useState(false)

  return (
    <div className="space-y-12">
      {/* === Кнопки === */}
      <SubSection
        title="Кнопки"
        description="Иерархия: primary → secondary → ghost. Danger варианты — для деструктивных действий."
        columns={2}
      >
        <Demo title="Варианты" note="<Button variant=...>">
          <Button>Сохранить</Button>
          <Button variant="secondary">Отмена</Button>
          <Button variant="ghost">Подробнее</Button>
          <Button variant="danger">Удалить</Button>
          <Button variant="danger-ghost">Удалить</Button>
          <Button variant="success">Подтвердить</Button>
        </Demo>

        <Demo title="Размеры" note="size='xs|sm|md|lg'">
          <Button size="xs">XS</Button>
          <Button size="sm">SM</Button>
          <Button size="md">MD</Button>
          <Button size="lg">LG</Button>
        </Demo>

        <Demo title="С иконкой" note="icon={Plus}">
          <Button icon={Plus}>Добавить</Button>
          <Button variant="secondary" icon={Edit3}>
            Редактировать
          </Button>
          <Button variant="ghost" icon={Download}>
            Экспорт
          </Button>
        </Demo>

        <Demo title="Состояния">
          <Button loading>Loading…</Button>
          <Button disabled>Disabled</Button>
          <PermissionGate allowed={false}>
            <Button>Без прав (hover для tooltip)</Button>
          </PermissionGate>
        </Demo>

        <Demo title="IconButton">
          <IconButton aria-label="Редактировать" icon={Edit3} />
          <IconButton aria-label="Удалить" icon={Trash2} variant="danger" />
          <IconButton aria-label="Настройки" icon={Settings} />
          <IconButton aria-label="Активна" icon={Bell} active />
          <IconButton aria-label="Поиск primary" icon={Search} variant="primary" />
        </Demo>

        <Demo title="Размеры IconButton">
          <IconButton aria-label="sm" icon={Settings} size="sm" />
          <IconButton aria-label="md" icon={Settings} size="md" />
          <IconButton aria-label="lg" icon={Settings} size="lg" />
        </Demo>
      </SubSection>

      {/* === Базовые поля (Input variants через TextField) === */}
      <SubSection
        title="Базовые поля"
        description="Высота 32px, focus chrome — обводка цвета primary. Здесь показан компонент TextField — единый шим над `<input>` для всех простых форм."
        columns={2}
      >
        <Demo title="Текст">
          <div className="w-full">
            <TextField id="a-text" value="" onChange={() => null} placeholder="Введите текст…" />
          </div>
        </Demo>

        <Demo title="С иконкой">
          <div className="w-full">
            <TextField
              id="a-search"
              value=""
              onChange={() => null}
              prefix={Search}
              placeholder="Поиск…"
            />
          </div>
        </Demo>

        <Demo title="Mono">
          <div className="w-full">
            <TextField id="a-mono" value="VUK-BLK-S-2026" onChange={() => null} mono />
          </div>
        </Demo>

        <Demo title="Error">
          <div className="w-full">
            <TextField
              id="a-err"
              value=""
              onChange={() => null}
              error="Обязательное поле"
              placeholder="Введи значение"
            />
          </div>
        </Demo>

        <Demo title="Disabled">
          <div className="w-full">
            <TextField id="a-dis" value="Read-only" onChange={() => null} disabled />
          </div>
        </Demo>

        <Demo title="С suffix">
          <div className="w-full">
            <TextField
              id="a-suf"
              value="2 890"
              onChange={() => null}
              suffix={Info}
              hint="suffix-слот (иконка справа)"
            />
          </div>
        </Demo>
      </SubSection>

      {/* === Селекторы === */}
      <SubSection title="Селекторы (Checkbox / Radio / Toggle / Slider)" columns={2}>
        <Demo title="Checkbox">
          <div className="flex flex-col gap-2">
            <Checkbox
              id="a-c1"
              checked={check1}
              onChange={setCheck1}
              label="Доступно к продаже"
            />
            <Checkbox
              id="a-c2"
              checked={check2}
              onChange={setCheck2}
              label="Подарочная упаковка"
            />
            <Checkbox
              id="a-c3"
              checked={false}
              indeterminate
              onChange={() => null}
              label="Все размеры (частично)"
            />
            <Checkbox
              id="a-c4"
              checked={false}
              onChange={() => null}
              label="Disabled"
              disabled
            />
          </div>
        </Demo>

        <Demo title="Radio">
          <div className="flex flex-col gap-2">
            <Radio
              id="a-r1"
              name="ds-radio"
              value="a"
              checked={radioValue === "a"}
              onChange={setRadioValue}
              label="WB"
            />
            <Radio
              id="a-r2"
              name="ds-radio"
              value="b"
              checked={radioValue === "b"}
              onChange={setRadioValue}
              label="Ozon"
            />
            <Radio
              id="a-r3"
              name="ds-radio"
              value="c"
              checked={radioValue === "c"}
              onChange={setRadioValue}
              label="Сайт"
            />
          </div>
        </Demo>

        <Demo title="Toggle">
          <div className="flex flex-col gap-2">
            <Toggle id="a-t1" on={toggleA} onChange={setToggleA} label="Уведомления" />
            <Toggle id="a-t2" on={false} onChange={() => null} label="Тёмная тема" />
            <Toggle id="a-t3" on={true} onChange={() => null} label="Disabled (on)" disabled />
          </div>
        </Demo>

        <Demo title="Slider">
          <div className="w-full">
            <Slider
              id="a-sl"
              value={sliderValue}
              onChange={setSliderValue}
              suffix="%"
              label="Объём"
            />
          </div>
        </Demo>
      </SubSection>

      {/* === Бейджи и теги === */}
      <SubSection title="Бейджи и теги" columns={2}>
        <Demo title="StatusBadge" note="STATUS_MAP[id]">
          {[1, 2, 3, 4, 5].map((id) => (
            <StatusBadge key={id} statusId={id} />
          ))}
        </Demo>

        <Demo title="StatusBadge — без dot">
          {[1, 2, 3, 4, 5].map((id) => (
            <StatusBadge key={id} statusId={id} dot={false} />
          ))}
        </Demo>

        <Demo title="LevelBadge" note="<LevelBadge level=...>">
          <LevelBadge level="model" />
          <LevelBadge level="variation" />
          <LevelBadge level="artikul" />
          <LevelBadge level="sku" />
        </Demo>

        <Demo title="PriorityBadge" note="<PriorityBadge level='P0'..'P3'>">
          <PriorityBadge level="P0" />
          <PriorityBadge level="P1" />
          <PriorityBadge level="P2" />
          <PriorityBadge level="P3" />
        </Demo>

        <Demo title="Badge — цветовые варианты" full>
          <Badge>default</Badge>
          <Badge variant="emerald">emerald</Badge>
          <Badge variant="blue">blue</Badge>
          <Badge variant="amber">amber</Badge>
          <Badge variant="red">red</Badge>
          <Badge variant="rose">rose</Badge>
          <Badge variant="purple">purple</Badge>
          <Badge variant="orange">orange</Badge>
          <Badge variant="teal">teal</Badge>
          <Badge variant="indigo">indigo</Badge>
          <Badge variant="emerald" dot>
            +12.4%
          </Badge>
          <Badge variant="rose" dot compact>
            −2.1%
          </Badge>
          <Badge variant="blue" icon={Info}>
            Новое
          </Badge>
          <Badge variant="amber" icon={AlertTriangle}>
            Внимание
          </Badge>
        </Demo>

        <Demo title="Tag">
          <Tag>gray</Tag>
          <Tag color="blue" icon={Hash}>
            collection
          </Tag>
          <Tag color="emerald">SKU</Tag>
          <Tag color="purple">brand</Tag>
          <Tag color="orange">promo</Tag>
          <Tag color="red" onRemove={() => null}>
            removable
          </Tag>
        </Demo>

        <Demo title="Chip / FilterChip">
          <Chip>Vuki</Chip>
          <Chip onRemove={() => null}>Чёрный</Chip>
          <Chip onRemove={() => null}>S, M, L</Chip>
          <FilterChip selected={filterA} onClick={() => setFilterA((v) => !v)}>
            Активные
          </FilterChip>
          <FilterChip selected={filterB} onClick={() => setFilterB((v) => !v)}>
            Архив
          </FilterChip>
        </Demo>

        <Demo title="Kbd">
          <Kbd>⌘</Kbd>
          <Kbd>⇧</Kbd>
          <Kbd>K</Kbd>
          <span className="text-xs text-muted">— открыть поиск</span>
          <Kbd>Enter</Kbd>
        </Demo>
      </SubSection>

      {/* === Аватары === */}
      <SubSection title="Аватары" columns={2}>
        <Demo title="Размеры">
          <Avatar initials="ДВ" size="xs" />
          <Avatar initials="ДВ" size="sm" />
          <Avatar initials="ДВ" size="md" />
          <Avatar initials="ДВ" size="lg" />
          <Avatar initials="ДВ" size="xl" />
        </Demo>

        <Demo title="Цвета">
          <Avatar initials="ДВ" color="stone" />
          <Avatar initials="АА" color="emerald" />
          <Avatar initials="МК" color="blue" />
          <Avatar initials="СП" color="purple" />
          <Avatar initials="НТ" color="rose" />
          <Avatar initials="РЛ" color="amber" />
          <Avatar initials="ВТ" color="teal" />
        </Demo>

        <Demo title="Со статусом">
          <Avatar initials="ДВ" status="online" />
          <Avatar initials="АА" color="emerald" status="busy" />
          <Avatar initials="МК" color="blue" status="offline" />
        </Demo>

        <Demo title="AvatarGroup">
          <AvatarGroup
            size="md"
            max={4}
            users={[
              { initials: "ДВ", color: "stone" },
              { initials: "АА", color: "emerald" },
              { initials: "МК", color: "blue" },
              { initials: "СП", color: "purple" },
              { initials: "НТ", color: "rose" },
              { initials: "РЛ", color: "amber" },
            ]}
          />
        </Demo>
      </SubSection>

      {/* === Прогресс и состояния === */}
      <SubSection title="Прогресс и состояния" columns={2}>
        <Demo title="ProgressBar">
          <div className="space-y-2 w-full">
            <ProgressBar value={85} color="emerald" />
            <ProgressBar value={60} color="blue" />
            <ProgressBar value={40} color="amber" />
            <ProgressBar value={20} color="red" />
            <ProgressBar value={30} color="stone" />
          </div>
        </Demo>

        <Demo title="Ring (CompletenessRing)">
          <div className="flex items-center gap-3 flex-wrap">
            <Ring value={0.92} size={32} />
            <span className="text-xs tabular-nums text-secondary">92%</span>
            <Ring value={0.65} size={32} />
            <span className="text-xs tabular-nums text-secondary">65%</span>
            <Ring value={0.42} size={32} />
            <span className="text-xs tabular-nums text-secondary">42%</span>
            <Ring value={0.18} size={32} />
            <span className="text-xs tabular-nums text-secondary">18%</span>
            <Ring value={70} inputScale="percent" size="md" label={<span>70%</span>} />
          </div>
        </Demo>

        <Demo title="ColorSwatch">
          <ColorSwatch hex="#1C1917" label />
          <ColorSwatch hex="#E11D48" label />
          <ColorSwatch hex="#059669" label />
          <ColorSwatch hex="#7C3AED" label size={20} />
          <ColorSwatch hex="#2563EB" size={24} />
        </Demo>

        <Demo title="Skeleton">
          <div className="space-y-2 w-full">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-64" />
            <Skeleton className="h-3 w-32" />
            <Skeleton className="h-10 w-20 rounded-full" />
          </div>
        </Demo>
      </SubSection>

      {/* === Tooltip === */}
      <SubSection title="Tooltip">
        <Demo title="Hover для тултипа" full>
          <div className="flex items-center gap-4 flex-wrap">
            <Tooltip text="Стандартный тултип (top)">
              <Button variant="secondary">Top</Button>
            </Tooltip>
            <Tooltip text="Снизу" position="bottom">
              <Button variant="secondary">Bottom</Button>
            </Tooltip>
            <Tooltip text="Слева" position="left">
              <Button variant="secondary">Left</Button>
            </Tooltip>
            <Tooltip text="Справа" position="right">
              <Button variant="secondary">Right</Button>
            </Tooltip>
            <Tooltip
              content={
                <span>
                  ReactNode <strong>content</strong>
                </span>
              }
            >
              <HelpCircle className="w-4 h-4 text-muted" />
            </Tooltip>
          </div>
        </Demo>
      </SubSection>
    </div>
  )
}
