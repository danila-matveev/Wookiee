# Wave 2 — Pages & Cards (6 параллельных агентов)

**Цель:** Реализовать все страницы и карточки каталога 1:1 с MVP.
**Параллелизация:** ДА — 6 worktree-агентов.
**Зависимость:** Wave 1 полностью завершена и в main.

## Архитектура

```
main (после Wave 1)
 ├── wave-2-b1-matrix          (Базовые модели + матрица)
 ├── wave-2-b2-registries      (Артикулы + SKU реестры)
 ├── wave-2-b3-modelcard       (Карточка модели)
 ├── wave-2-b4-colors          (Цвета + ColorCard)
 ├── wave-2-b5-skleyki         (Склейки + SkleykaCard)
 └── wave-2-b6-references      (Все справочники)
```

## Общие правила для всех 6 агентов

- Source of truth: `/Users/danilamatveev/Projects/Wookiee/redesign + PIX/wookiee_matrix_mvp_v4.jsx`
- Использовать atomic UI из Wave 1 (LevelBadge, StatusBadge, CompletenessRing, Fields, ColumnsManager, BulkActionsBar)
- Все мутации — через service.ts из Wave 1 A2
- TanStack Query: staleTime 60s, инвалидация после мутаций
- React Router DOM v7 useSearchParams — для модальных карточек (?model=X, ?color=Y)
- Screenshot diff после каждой страницы: открыть dev server, сравнить с MVP в браузере

---

## Агент B1 — MatrixView (Базовые модели)

### Промпт
```
Ты Wave 2 Agent B1 — страница «Базовые модели» (матрица) Wookiee Hub каталога.

Контекст:
- MVP компонент: MatrixView в wookiee_matrix_mvp_v4.jsx (строки ~600-1000)
- Текущий файл: src/pages/catalog/matrix.tsx (нужно переписать значительную часть)

Задачи:
1. **Подзаголовок** — «{N} моделей · {V} вариаций · {A} артикулов · {S} SKU»
   - Считается из агрегатов: count(modeli_osnova WHERE status != Архив), count(modeli), count(artikuly), count(tovary)
2. **Кнопка «Экспорт»** — справа от подзаголовка, открывает диалог CSV/XLSX (заглушка пока — alert «TODO»)
3. **Filter chips:**
   - Категории (chips, multi-select)
   - Коллекции (chips, multi-select)
   - **Status chips** — все 7 model-статусов из statusy WHERE tip='model', с counts
   - «Незаполненные» (toggle) — модели с completeness < 0.5
   - **Search** — по kod, nazvanie_etiketka, artikuly→OZON, tovary→barkod
4. **GroupBy** — Select «Без / По категории / По коллекции / По фабрике / По статусу»
5. **Таблица:**
   - Чекбокс-колонка для bulk
   - Раскрытие вариаций (chevron)
   - kod, nazvanie_etiketka, kategoriya, kollekciya, fabrika
   - **Колонка «Статус»** — StatusBadge (КРИТИЧНО — это то самое первое жалобное замечание)
   - Размеры — chip-pills
   - Цвета модели — кружочки swatches с hex
   - Заполненность — CompletenessRing (мини, 16px)
   - More menu (Edit/Duplicate/Archive) на hover
6. **Раскрытие вариаций** — React.Fragment с key={`${model.kod}-variations`}
7. **Tooltip на «·»** когда вариаций <2
8. **BulkActionsBar** при выделении строк:
   - «Изменить статус» (выпадашка model-статусов)
   - «Дублировать» (создать копию каждой)
   - «Экспорт выбранного»
   - «Архивировать»
9. **Click по строке** → открывает ?model=KOD (модальная ModelCard, но её делает B3)

Verify:
- Открыть /catalog в dev, увидеть колонку «Статус»
- Status chips отрабатывают, фильтр работает
- BulkActionsBar появляется при выделении
- Screenshot vs MVP — должно быть структурно идентично

Когда готово — git commit, push в ветку wave-2-b1-matrix.
```

---

## Агент B2 — Registries (Артикулы + SKU)

### Промпт
```
Ты Wave 2 Agent B2 — реестры артикулов и SKU.

Файлы:
- src/pages/catalog/artikuly.tsx (или registry.tsx)
- src/pages/catalog/tovary.tsx (или sku.tsx)

### Артикулы
Колонки (11 в ColumnsManager, по умолчанию 7):
1. Артикул (kod) — default
2. Модель (kod_modeli + nazvanie) — default
3. Цвет (color_ru + swatch) — default
4. Статус артикула (StatusBadge) — default
5. WB-номенклатура — default
6. OZON-артикул — default
7. Создан — default
8. Обновлён
9. Категория
10. Коллекция
11. Производитель

- Search: по WB-номенклатуре + OZON-артикулу + kod_artikula + kod_modeli + color_ru
- Status filter chips: все 3 artikul-статуса (Запуск/Продается/Выводим)
- BulkActionsBar: изменить статус, экспорт

### SKU (Tovary) реестр
Колонки (17 в ColumnsManager, по умолчанию 9):
1. Баркод (default)
2. Артикул (kod_artikula) (default)
3. Модель (default)
4. Цвет (default)
5. Размер (default)
6. WB-номенклатура (default)
7. OZON-артикул (default)
8. Статус WB (default)
9. Статус OZON (default)
10. Статус Сайт
11. Статус Lamoda
12. Барко GS1
13. Баркод GS2
14. Баркод перехода
15. Цена WB
16. Цена OZON
17. Дата создания

- **GroupBy:** none | model | color | size | collection | channel
- **Status group filter** (4 опции: Все/Активные/Архив/Без статуса)
- **Channel filter** (Все/WB/OZON/Сайт/Lamoda) — оставить из текущего кода
- **Composite search** «Audrey/black/S» — split по «/», искать кросс-полевой:
  - токен 1 → kod_modeli или nazvanie_etiketka
  - токен 2 → color_ru или color_en
  - токен 3 → razmer_kod
- **Inline edit статусов** — клик по StatusBadge в строке → выпадашка статусов того же tip
- **Bulk «Привязать к склейке»** — модалка выбора склейки, привязывает выделенные SKU
- **Заголовки групп** при groupBy != none — большие, с count

Verify:
- /catalog/articles и /catalog/sku открываются
- ColumnsManager сохраняет настройки в ui_preferences
- GroupBy работает, заголовки появляются
- Composite search «Wookiee/чёрный/S» возвращает правильные SKU

Когда готово — git commit, push в ветку wave-2-b2-registries.
```

---

## Агент B3 — ModelCard (карточка модели)

### Промпт
```
Ты Wave 2 Agent B3 — карточка модели (ModelCard).

Контекст:
- MVP компонент: ModelCard в MVP-файле (строки ~1100-1700)
- Файл: src/pages/catalog/model-card.tsx (создать или переписать)
- Открывается через ?model=KOD в URL

Архитектура:
- editing: boolean, draft: ModelOsnova
- useEffect сбрасывает draft при открытии или смене editing
- Header: Сохранить / Отмена при editing, Дублировать / Архивировать / Закрыть в read mode

Layout:
- 2-колоночная сетка: 2/3 — основной контент (Tabs), 1/3 — Sidebar

### Header
- Большая иконка модели (color swatch первого цвета или плейсхолдер)
- kod (h1, Instrument Serif italic) + nazvanie_etiketka (subtitle)
- Кнопки: «Сохранить» / «Отмена» (edit) | «Редактировать» / «Дублировать» / «В архив» / «×» (read)
  - **Дублировать** — модалка «Введите новый kod» → service.duplicateModel(kod, newKod) → редирект на ?model=newKod
  - **В архив** — confirm «Архивировать модель и все вариации/артикулы/SKU?» → service.archiveModel(kod)

### Tabs (5)
1. **Описание**
   - Все ~30 атрибутивных полей с LevelBadge:
     - kategoriya (model), kollekciya (model), fabrika (model)
     - tip_kollekcii, status (model), notion_link, notion_strategy_link, yandex_disk_link
     - dlya_kakoy_grudi, stepen_podderzhki, forma_chashki, regulirovka, zastezhka, posadka_trusov, vid_trusov
     - naznachenie, stil, po_nastroeniyu, tegi (multiselect)
     - tnved, gruppa_sertifikata, nazvanie_sayt, opisanie_sayt, details (textarea), description (textarea)
     - material, sostav_syrya, composition
     - **Размерная линейка** (XS S M L XL XXL) как chip-pills с toggle (КРИТИЧНО)
   - В edit mode — все Field-ы из atomic UI с level prop
   - В read mode — текст + LevelBadge

2. **Атрибуты** — динамический список из ATTRIBUTES_BY_CATEGORY (Wave 1 A1)
   - Загружается по kategoriya_id модели
   - Например, для «Боди» — стиль, посадка, ткань, чашка...
   - Для каждого атрибута — Field с level prop

3. **Артикулы** — таблица артикулов модели
   - Header: «+ Добавить артикул» (модалка нового артикула: цвет, статус, WB, OZON)
   - Колонки: Цвет (swatch + название, кликабельно → ?color=COD), Артикул, Статус, WB, OZON
   - Click по цвету → открывает ColorCard (B4)

4. **SKU** — таблица всех SKU модели
   - Колонки: Баркод, Цвет, Размер, Канал, Статус
   - Inline edit статусов

5. **Контент**
   - Notion-карточка (notion_link) — preview iframe или ссылка-кнопка
   - Notion-стратегия (notion_strategy_link) — ссылка-кнопка
   - Яндекс.Диск (yandex_disk_link) — ссылка-кнопка
   - **Блок Упаковка** — selectField с upakovki, под ним preview габаритов и цены
   - **Блок Сертификаты** — список из modeli_osnova_sertifikaty, с file_link, кнопка «+ Сертификат»

### Sidebar
- **CompletenessRing 56px** — реальный расчёт по полям модели (не 0.7/0.3 хардкод)
- **Метрики** — продажи (заглушка), оборачиваемость, last update
- **Вариации** — список с +Добавить и tooltip на каждой
- **Цвета модели** — большие swatches с тултипами, click → ?color=COD

Verify:
- Кнопка «Редактировать» переключает в edit mode, поля становятся редактируемыми
- Сохранить вызывает updateModel и инвалидирует query
- Дублировать создаёт копию
- Архивировать каскадно меняет статусы
- Размерная линейка отображается как chip-pills (визуальный тест)

Когда готово — git commit, push wave-2-b3-modelcard.
```

---

## Агент B4 — Colors (ColorsView + ColorCard)

### Промпт
```
Ты Wave 2 Agent B4 — страница цветов и карточка цвета.

Файлы:
- src/pages/catalog/colors.tsx (ColorsView)
- src/pages/catalog/color-card.tsx (ColorCard)

### ColorsView
- Filter chips: Семейство (5 значений из semeystva_cvetov)
- Search: по color_code, color_ru, color_en
- Status filter
- Кнопка «+ Новый цвет» — модалка с hex picker (использовать react-colorful или нативный <input type="color">)

Группировка по семейству с заголовком (h3 + count):
- Audrey
- Jelly (бесшовный)
- Трикотаж
- Наборы
- Прочие

Таблица в каждой группе:
- Color Code (kod), Цвет RU (color_ru), Color EN (color_en, новое), Hex swatch (24px), Ластовица (boolean), Использован в (count of artikuly), Статус
- Hover MoreHorizontal: Edit/Delete

Click по строке → ?color=KOD (открывает ColorCard)

### ColorCard
- Header big swatch (40px) + color_code (h1) + color_ru/color_en
- Кнопки: Редактировать / Архивировать / Закрыть
- Body: 2/3 — Tabs

#### Tab 1: Артикулы (N)
- Все артикулы с этим цветом
- Колонки: Артикул, Модель, Статус, WB, OZON
- Click по модели → ?model=KOD (ModelCard)

#### Tab 2: Модели использующие этот цвет
- Список модели → count артикулов с этим цветом

### Sidebar ColorCard
- HEX 64px swatch + hex code (моноширинный)
- color picker (изменить hex, сохранить)
- Семейство (select)
- Статус (select)
- Ластовица (checkbox)
- «Похожие цвета» — 6 цветов с минимальным евклидовым расстоянием в RGB

Verify:
- /catalog/colors группирует по семейству
- Hex picker работает на «+ Новый цвет»
- ColorCard показывает «Артикулы (N)» с правильным count
- «Похожие цвета» возвращают 6 swatches

Когда готово — git commit, push wave-2-b4-colors.
```

---

## Агент B5 — Skleyki

### Промпт
```
Ты Wave 2 Agent B5 — склейки.

Файлы:
- src/pages/catalog/skleyki.tsx (SkleykaList)
- src/pages/catalog/skleyka-card.tsx (SkleykaCard) — уже есть, нужно довести до MVP

### SkleykaList
- Подзаголовок: «До 30 SKU в склейке. {N} активных, {M} архивных»
- Filter: канал (WB/OZON), статус
- Search по nazvanie / SKU в составе
- Кнопка «+ Создать склейку» — модалка
- Колонки таблицы:
  - Название
  - Канал (бейдж)
  - **Заполненность** — progress bar + cnt/30 (КРИТИЧНО)
  - Кол-во SKU
  - Создана
  - Статус

Click по строке → /catalog/skleyki/:id

### SkleykaCard (расширить существующий)
- Header: название + большой прогресс справа (CompletenessRing 80px на cnt/30)
- Tabs:
  1. SKU — таблица с Trash2 кнопкой unlink на каждой строке (BulkActionsBar тоже)
  2. Аналитика (заглушка)
  3. История

### Sidebar
- **«Правила склейки»** (3 чек-пункта из MVP):
  1. Один цвет, разные размеры
  2. ИЛИ один размер, разные цвета
  3. До 30 SKU
- **«Что это даёт?»** — описание буста ранжирования из MVP
- Метрики склейки

### Создание новой склейки
- Модалка: название, канал
- После создания — редирект на :id, добавление SKU через BulkActionsBar в /catalog/sku

Verify:
- Колонка «Заполненность» с progress bar
- Trash2 unlink работает
- Sidebar «Правила склейки» отображается
- Создание новой склейки работает E2E

Когда готово — git commit, push wave-2-b5-skleyki.
```

---

## Агент B6 — References (все справочники)

### Промпт
```
Ты Wave 2 Agent B6 — все справочники каталога.

Файлы:
- src/pages/catalog/kategorii.tsx
- src/pages/catalog/kollekcii.tsx
- src/pages/catalog/fabriki.tsx
- src/pages/catalog/importery.tsx
- src/pages/catalog/razmery.tsx
- src/pages/catalog/semeystva-cvetov.tsx (новый)
- src/pages/catalog/upakovki.tsx (новый)
- src/pages/catalog/kanaly-prodazh.tsx (новый)
- src/pages/catalog/sertifikaty.tsx (новый)

Общая структура каждой страницы:
- Subtitle (описание справочника)
- Filter / Search
- Кнопка «+ Добавить»
- Таблица с колонками
- Hover MoreHorizontal (Edit / Delete)
- RefModal (atomic UI Wave 1) для CRUD

### Категории
- Колонки: Название, Описание, Кол-во моделей (count), Created
- RefModal fields: nazvanie (text), opisanie (textarea)

### Коллекции
- Колонки: Название, Описание, Год запуска, Кол-во моделей
- RefModal fields: nazvanie, opisanie, god_zapuska (number)

### Производители
- Колонки: Название, Город, Контакт, Email, WeChat, Специализация, Lead time, Кол-во моделей
- RefModal fields: nazvanie, strana, gorod, kontakt, email, wechat, specializaciya, leadtime_dni (number), notes (textarea)

### Юрлица (Importery)
- Колонки: Short Name, Полное название, ИНН, КПП, ОГРН, Банк, Р/С, Контакт, Телефон
- RefModal fields: short_name, nazvanie, nazvanie_en, inn, kpp, ogrn, adres, bank, rs, ks, bik, kontakt, telefon

### Размеры
- Колонки: Код, Название, RU, EU, China, Порядок, Кол-во SKU
- RefModal fields: kod, nazvanie, ru, eu, china, poryadok (number)

### Семейства цветов (новая страница)
- Колонки: Код, Название, Описание, Кол-во цветов, Порядок
- RefModal fields: kod, nazvanie, opisanie, poryadok

### Упаковки (новая страница)
- Колонки: Название, Тип, Цена ¥, Габариты (ДxШxВ), Срок изготовления, file_link
- RefModal fields: nazvanie, tip (select: pakey/pakey_zip/korobka/korobka_print), price_yuan, dlina_cm, shirina_cm, vysota_cm, obem_l, srok_izgotovleniya_dni, file_link, notes

### Каналы продаж (новая страница)
- Колонки: Код, Название, Short, Color, Active, Порядок
- RefModal fields: kod, nazvanie, short, color, active (checkbox), poryadok

### Сертификаты (новая страница, таблица уже есть)
- Колонки: Название, Тип, Номер, Дата выдачи, Дата окончания, Орган, Группа, file_url
- RefModal fields: nazvanie, tip (select), nomer, data_vydachi (date), data_okonchaniya (date), organ_sertifikacii, gruppa_sertifikata, file_url

Verify:
- Все 9 справочников открываются через Sidebar
- RefModal работает на каждом (insert + update)
- Hover MoreHorizontal показывает Edit/Delete
- Поиск работает на каждой странице

Когда готово — git commit, push wave-2-b6-references.
```

---

## Параллельный запуск 6 агентов

```python
# Псевдокод оркестратора:
parallel_tasks = [
    Agent(B1_prompt, isolation='worktree', branch='wave-2-b1-matrix'),
    Agent(B2_prompt, isolation='worktree', branch='wave-2-b2-registries'),
    Agent(B3_prompt, isolation='worktree', branch='wave-2-b3-modelcard'),
    Agent(B4_prompt, isolation='worktree', branch='wave-2-b4-colors'),
    Agent(B5_prompt, isolation='worktree', branch='wave-2-b5-skleyki'),
    Agent(B6_prompt, isolation='worktree', branch='wave-2-b6-references'),
]
results = parallel_tasks.run_concurrently()
```

После всех 6 → merge в main → Wave 2 verification.

## Verification Wave 2
- [ ] Все 6 PR смержены без конфликтов
- [ ] npm run build / lint — 0 errors
- [ ] Dev server: все страницы открываются
- [ ] Колонка «Статус» в матрице ПРИСУТСТВУЕТ
- [ ] ModelCard: edit/save работает
- [ ] ModelCard: дублирование работает
- [ ] ModelCard: архивирование каскадное
- [ ] Размерная линейка как chip-pills
- [ ] LevelBadge на всех полях ModelCard
- [ ] ColorCard: «Артикулы (N)» работает
- [ ] Skleyki: колонка «Заполненность»
- [ ] Все 9 справочников + новые 3 (семейства, упаковки, каналы)

После прохождения → запуск Wave 3.
