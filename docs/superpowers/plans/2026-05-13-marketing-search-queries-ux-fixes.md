# Marketing → Поисковые запросы — UX-фиксы по фидбеку 2026-05-13

**Worktree:** `.claude/worktrees/marketing-v4-fidelity`
**Branch:** `feature/marketing-v4-fidelity-phase2b`
**Базовый коммит:** `d28cbc0` (HEAD на старте)
**Статус Phase 2A:** уже на prod, бэкенд работает (25+23+277 = 325 записей).

## Контекст

После выкатки Phase 2A пользователь нашёл 10 проблем UX/верстки, которые не позволяют нормально пользоваться экраном.
Корень — карточка деталей в split-pane сжимает таблицу до 800px (теряются 4 правые колонки),
внутренний скролл карточки не работает, кнопка ✕ незаметна, чипы-фильтры занимают место,
нет колонки/фильтра статуса, у брендов нет метрик («появятся после Phase 2B»),
кнопка Обновить возвращает 401.

Этот план решает всё перечисленное за один цикл, по этапам с проверкой на каждом.

## Decisions (приняты до старта без уточнения)

| # | Решение | Альтернатива | Почему |
|---|---|---|---|
| D1 | Detail = drawer-overlay 720px справа (всегда, для всех viewport) | Route-based отдельная страница | Минимум кода, переиспользует существующий Drawer. Route-based — отдельным заходом, если понадобится. |
| D2 | Section sidebar «Маркетинг» (176px) — спрятать на страницах Marketing | Сделать collapsible | На двух страницах раздела sidebar дублирует то, что в icon-bar. Простой `<aside hidden>` — без лишних toggle-кнопок. |
| D3 | Метрики брендов: только те, что есть в `search_query_product_breakdown`: open_card → «Открытия», add_to_cart → «Корзина», orders → «Заказы». Частота/Переходы для брендов — `null` (явно «нет данных»). НЕ смешивать open_card с frequency. | Подменять `frequency` на `open_card` | Это разные события WB-аналитики: показы запроса в выдаче ≠ открытия карточки. Сложение их даст ложную метрику. |
| D4 | Бренд-форма — поле `canonical_brand` спрятать под expandable «Расширенно» | Удалить совсем | Алиасы (вуки→wookiee) кому-то всё-таки нужны. Спрячем, не покажем по умолчанию. |
| D5 | Refresh auth: Hub получает supabase JWT из сессии, кладёт в `Authorization: Bearer ...`, analytics-api проверяет в middleware | Сервисный токен | JWT уже есть в каждом запросе с фронта — не вводим новый секрет. |

## Phases

### Phase 1 — Detail panel: drawer overlay вместо split-pane (P0.1)

**Goal:** Открытие WW/артикула/бренда показывает полноэкранный drawer справа (720px), таблица под ним не сжимается, ✕ виден, внутренний скролл работает.

**Tasks:**

1. `wookiee-hub/src/pages/marketing/search-queries.tsx`:
   - Удалить ветку `active.kind === 'detail' && isWide` со split-pane `<aside w-[560px]>`.
   - Все режимы → `renderPanel('drawer')` (включая detail).
   - Удалить импорт `useMediaQuery` если больше не нужен.
2. `wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx`:
   - В `mode='drawer'` ветке у `<Drawer>` указать `width="lg"` (720px) — добавить prop в Drawer если нет.
   - Шапку drawer с явным `<X size={20}>` button в правом верхнем углу проверить — Drawer уже имеет close, но проверить что кликабельно и заметно.
3. То же для `wookiee-hub/src/pages/marketing/promo-codes.tsx` + `PromoDetailPanel.tsx` — drawer-only.
4. Если `Drawer` компонент не поддерживает кастомную ширину — добавить prop `width: 'sm'|'md'|'lg'|'xl'` с маппингом `420/520/720/920`.

**Verification:**
- При открытии любого WW-кода drawer выезжает справа на 720px.
- Таблица под drawer показывает все 12 колонок (CR корз / Корз / CR зак / Заказы / CRV видны).
- ✕ кнопка в правом верхнем углу drawer работает + крупная.
- Внутри drawer прокрутка мышью доходит до футера «Итого по N товарам».
- При viewport 1280, 1600, 1920 — поведение одинаковое (drawer всегда overlay).

**Rollback:** Один git revert этого коммита возвращает split-pane.

---

### Phase 2 — Колонка «Статус» + фильтр + смена статуса в строке (P0.2 / P0.3 / P0.4)

**Goal:** В таблице видна колонка «Статус», клик по бейджу открывает popover для смены, в шапке таблицы новый фильтр «Статус».

**Tasks:**

1. `SearchQueriesTable.tsx`:
   - Добавить колонку «Статус» между «Кампания» и «Частота». colgroup: добавить `<col className="w-[100px]" />`.
   - В `<thead>` `<th className={TH}>Статус</th>` (после Кампания, перед Частота).
   - В `SectionGroup` row рендер: добавить `<td>` с `<StatusEditor row={r} />` (компонент уже существует, переиспользовать). Если StatusEditor сейчас inline в DetailPanel — извлечь.
2. URL state: `?status=active|free|archive|all` (default `all`).
3. В `filtered` useMemo добавить фильтрацию по statusFilter: `STATUS_DB_TO_UI[r.status] === statusFilter` (если != all).
4. В шапке фильтров — компонент `<StatusFilterChips>` (как existing chip-фильтры, но 4 варианта). Или сразу в виде Select.
5. Optimistic update в `useUpdateSearchQueryStatus` уже работает.

**Verification:**
- Колонка «Статус» видна, в каждой строке цветной бейдж (зелёный/синий/серый).
- Клик на бейдж → popover с 3 вариантами → выбор сменяет статус оптимистично + сохраняет в DB.
- Фильтр работает: при `Свободен` показывает только paused-строки.

---

### Phase 3 — Фильтры Модель/Назначение → выпадающие списки + стили (P1.5 / P1.6)

**Goal:** Чипы-фильтры заменить на дропдауны с поиском, сэкономить вертикаль. Починить стиль «Группировка».

**Tasks:**

1. `SearchQueriesTable.tsx` шапка фильтров:
   - Заменить блок «Модель: [chips]» на `<DropdownFilter label="Модель" value={modelF} options={uniqueModels} onChange={setModelF} searchable />`.
   - То же для «Назначение».
   - Если такого компонента нет — создать в `components/marketing/DropdownFilter.tsx` на базе Radix Select или Popover+Combobox.
2. Группировка стиль: проверить что `GroupBySelector` рендерит обычным размером, не bold. Сравнить с `feature/marketing-v4-fidelity-phase2b` HEAD до моих правок (commit `6e4b298`) — что-то поменялось.
3. Sidebar «Маркетинг» 176px скрыть (D2):
   - В `MarketingLayout` или в `pages/marketing/*.tsx` обёртке убрать `<aside w-44>` рендер, оставить только icon-bar навигацию.

**Verification:**
- Фильтры Модель/Назначение — компактные дропдауны (1 строка).
- Группировка дропдаун такой же визуально (не жирный).
- На странице `/marketing/search-queries` нет вертикального sidebar «Маркетинг» слева — main расширился ещё на 176px.

---

### Phase 4 — Метрики для брендов (P2.8)

**Goal:** В detail panel брендов (wooki, Вуки, Мун) видны конкретные числа Открытий/Корзин/Заказов из breakdown, не «появятся после Phase 2B».

**Tasks:**

1. БД (Supabase MCP) — обновить тип `SearchQueryStatsAgg` чтобы добавить честные null-able поля:
   - Расширить return type RPC: `frequency, transitions, open_card, additions, orders` (где open_card — отдельная колонка, не подмена frequency).
   - Для `entity_type = 'brand'`: `frequency=NULL, transitions=NULL, open_card=SUM(open_card), additions=SUM(add_to_cart), orders=SUM(orders)` из JOIN на `search_query_product_breakdown` по `search_word=u.query_text`.
   - Для `entity_type IN ('nm_id', 'ww')`: оставить как было — `frequency, transitions, additions, orders` из weekly, `open_card=NULL` (мы это не считаем по WW отдельно).
   - НЕ суммировать поля разных семантик. Open_card складывается только с open_card.
2. Frontend `types/marketing.ts`:
   - В `SearchQueryStatsAgg` добавить `open_card: number | null`, сделать `frequency, transitions, additions, orders` тоже nullable.
3. `SearchQueriesTable.tsx`:
   - В таблице где сейчас «Частота», для брендов показывать «—» (если `frequency===null`). Возможно добавить отдельную колонку «Откр.» для брендов (или показывать в той же позиции как fallback).
   - Решение по UI колонок: оставить колонку «Частота» — для брендов в ней «—», открытия видны в детальной карточке.
4. `SearchQueryDetailPanel.tsx`:
   - Блок «За выбранный период» рендерит набор плиток: Частота / Переходы / Открытия / Корзина / Заказы / CR-метрики.
   - Каждая плитка скрывается, если значение `null` (для брендов скрываются Частота, Переходы и связанные CR).
   - Для бренда: видны Открытия, Корзина, Заказы + честная подпись «По карточкам товаров».
5. Сводная таблица в нижней части (По товарам) — оставить как есть, она уже корректно работает для всех 3 типов.

**Verification:**
- Открыть detail wooki → видны числа **только** Открытия / Корзина / Заказы (Частота и Переходы — отсутствуют, не показаны).
- НЕ видна заглушка «Метрики появятся после Phase 2B».
- Подпись блока: «По карточкам товаров (за выбранный период)».
- НЕ суммированы в одно число open_card + frequency.
- WW/артикул detail работают как раньше — Частота, Переходы, Корзина, Заказы из weekly.
- В таблице списка для брендов в колонке «Частота» стоит «—» (нет данных), не путаемся с open_card.

---

### Phase 5 — Refresh button auth (P2.9)

**Goal:** Кнопка «Обновить» реально дёргает analytics-api → запускает ETL `wb-analytics-sync` → пишет в Supabase.

**Tasks:**

1. `wookiee-hub/src/hooks/marketing/use-sync-log.ts` (или где `useTriggerSync`):
   - Перед fetch получить supabase JWT: `const session = (await supabase.auth.getSession()).data.session`.
   - В `fetch(...)` добавить `headers: { Authorization: 'Bearer ' + session.access_token }`.
2. `services/analytics_api/marketing.py` (или middleware):
   - Проверить что endpoint `/api/marketing/sync/{job}/refresh` валидирует JWT через supabase JWKS.
   - Если нет — добавить middleware, отбрасывать без токена.
   - Если есть — проверить почему сейчас 401 (может, ожидается другой header name).
3. Локально не тестируем (нужен прод-Supabase) — деплой analytics-api после правки.

**Verification:**
- Клик «Обновить» в DevTools Network → запрос с `Authorization: Bearer eyJ...`.
- Ответ 200 + строка sync_log с `status='running'`.
- Через ~30 сек статус меняется на `success` + lastUpdate в UpdateBar обновляется.

**Risk:** Может потребоваться дополнить analytics-api JWT-валидацию. Если такого middleware нет — это +1 час.

---

### Phase 6 — Бренд-форма: спрятать canonical_brand под «Расширенно» (P3.10)

**Goal:** Базовое создание бренда — одно поле «Поисковый запрос». Canonical_brand — под раскрываемой секцией для тех, кому нужны алиасы.

**Tasks:**

1. `AddBrandQueryPanel.tsx`:
   - Поле `canonical_brand` обернуть в `<details><summary>Алиас бренда (опционально)</summary>...</details>`.
   - Helper-текст переписать: «Если "вуки" — это другое написание "wookiee", укажи canonical = wookiee. Тогда "вуки" сгруппируется с другими формами этого же бренда.»
   - Дефолт = `query.toLowerCase()` остаётся.

**Verification:**
- При открытии формы видно только 2 поля: «Поисковый запрос» и «Заметки».
- Раскрытие «Алиас бренда» показывает поле + помощь.

---

### Phase 7 — Финальный E2E + деплой

**Goal:** Все правки на prod, пройдены глазами через Playwright + ручная проверка.

**Tasks:**

1. `pnpm build` без ошибок.
2. `rsync -avz --delete dist/ timeweb:/home/danila/projects/wookiee/wookiee-hub/dist/`.
3. Если Phase 5 затронул analytics-api — задеплоить отдельно.
4. Playwright UAT по чек-листу:
   - Список 325 строк, видна колонка «Статус», все 13 колонок поместились.
   - Клик статуса меняет.
   - Фильтр «Статус: Свободен» отфильтровывает.
   - Фильтры Модель/Назначение — дропдауны, sidebar «Маркетинг» нет.
   - Открыть WW → drawer 720px, ✕ виден, скролл до низа товаров работает.
   - Открыть бренд wooki → метрики РЕАЛЬНЫЕ (не «после Phase 2B»).
   - Создать бренд «тест» → одно поле, не спрашивает canonical.
   - Кнопка «Обновить» → запрос проходит, статус `running`.
5. Скриншоты прод (либо снимки DOM-snapshot если screenshots таймаутят).
6. Сообщить пользователю результат — ждать ОК.

**Verification:**
- Все 6 фаз отмечены в чек-листе как «прошло».
- 0 console.error на prod при загрузке списка/детали/добавления.

---

### Phase 8 — Commit + push

**Goal:** Зафиксировать все правки одной серией коммитов с понятными сообщениями.

**Tasks:**

1. `git add -p` по фазам, atomic commits:
   - `feat(marketing): detail panel — drawer overlay вместо split-pane`
   - `feat(marketing): колонка статуса в таблице + фильтр + inline-смена`
   - `refactor(marketing): фильтры Модель/Назначение → дропдауны, скрыть sidebar`
   - `feat(marketing-db): метрики брендов через product_breakdown агрегат`
   - `fix(marketing): refresh button auth — пробрасываем supabase JWT`
   - `refactor(marketing): бренд-форма — canonical_brand под details`
2. Push в `feature/marketing-v4-fidelity-phase2b`.
3. Не мерджу — ждём ОК пользователя.

---

## Notes

- **Не делаю в этом плане:** обновление UI промокодов до новых дропдаунов (отдельная задача), pagination таблицы (325 строк рендерятся OK), экспорт в csv, история изменений статуса.
- **Если после Phase 1 окажется** что drawer 720px тоже мало для breakdown 5 колонок — расширить до 800 или ввести горизонтальный скролл внутри таблицы breakdown.
- **Если Phase 4 покажет** что `search_query_product_breakdown` для бренда «wooki» пустой — значит ETL не пишет туда (только для WW-кодов). Тогда Phase 4 переоформляется в задачу для следующей итерации с правкой ETL.
