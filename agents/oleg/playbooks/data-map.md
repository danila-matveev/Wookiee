# Data Map — Tool → Data → Report Sections

> Карта связей: инструмент → данные → секции отчёта.
> Используется оркестратором для pre-flight проверок (Phase 3) и агентами для понимания какие инструменты вызывать.
> Покрывает ВСЕ агенты: reporter, marketer, funnel.

---

## Tool → Data → Report Sections

| Tool | Agent | Data Returned | Used In Sections | Report Types |
|------|-------|--------------|-----------------|--------------|
| `get_brand_finance` | reporter | маржа, маржинальность, выручка до СПП, заказы (шт, ₽), продажи шт, реклама (внутр/внешн), ДРР% (от продаж и от заказов), СПП%, оборачиваемость_дни, годовой_ROI | § Ключевые изменения (Бренд), § Сведение ΔМаржи, § Топ-выводы | daily, weekly, monthly |
| `get_channel_finance` | reporter | детальные финансы канала (wb/ozon): маржа, выручка, заказы, продажи, реклама (внутр/внешн отдельно), логистика, хранение, себестоимость, комиссия, СПП%, ДРР%, НДС, штрафы, удержания | § Wildberries, § OZON, § Структура затрат | daily, weekly, monthly |
| `get_model_breakdown` | reporter | декомпозиция по моделям (model_osnova): маржа, продажи, реклама (внутр/внешн), ДРР, остатки FBO, собственный склад, транзит, итого остатки, оборачиваемость (FBO и все), годовой ROI | § Модельная декомпозиция WB/OZON, § Модели — драйверы/антидрайверы | daily, weekly, monthly |
| `get_daily_trend` | reporter | дневная динамика канала: маржа, выручка, заказы, продажи, реклама по каждому дню | § Дневная динамика (при необходимости) | daily, weekly |
| `get_advertising_stats` | reporter | реклама WB: показы, клики, CTR, CPC, расход, заказы через рекламу, корзины + производные (CPM, CPL, CPO, CR); органическая воронка: card_opens, add_to_cart, orders, выкупы с конверсиями | § Воронка продаж WB, § Реклама WB, § Ключевые изменения (Бренд) | daily, weekly, monthly |
| `get_model_advertising` | reporter | рекламная статистика WB по моделям: показы, клики, расход, корзины, заказы, CTR, CPC, CPM, CPL, CPO, конверсии | § Реклама WB (детальная), § Модели — драйверы/антидрайверы | weekly, monthly |
| `get_orders_by_model` | reporter | заказы по моделям: количество заказов, сумма заказов ₽, сравнение с предыдущим периодом | § Модельная декомпозиция, § Модели — драйверы/антидрайверы | daily, weekly, monthly |
| `get_margin_levers` | reporter | декомпозиция маржи по 5 рычагам: цена до СПП, СПП%, ДРР (внутр/внешн), логистика ₽/ед, себестоимость ₽/ед. Рублёвый вклад каждого фактора | § Сведение ΔМаржи (Reconciliation), § Топ-выводы | daily, weekly, monthly |
| `get_weekly_breakdown` | reporter | понедельная разбивка финансов канала: маржа, выручка, заказы, реклама, логистика | § Динамика по неделям (в месячных отчётах) | monthly |
| `validate_data_quality` | reporter | проверка качества данных WB: retention==deduction, корректировка маржи | § Паспорт отчёта (Полнота данных) | daily, weekly, monthly |
| `get_product_statuses` | reporter | статусы всех товаров: артикул → статус (активный, архив) | § Анализ по статусам WB | weekly, monthly |
| `calculate_metric` | reporter | калькулятор для верификации расчётов | вспомогательный | all |
| `get_plan_vs_fact` | reporter, marketer | план, факт MTD, план MTD, % выполнения, прогноз, статус (ahead/on_track/behind), топ-модели по отклонению | § План-факт | weekly, monthly |
| `get_price_elasticity` | reporter | ценовая эластичность модели (log-log OLS): β, R², p-value | § Ценовой анализ | weekly, monthly |
| `get_price_recommendation` | reporter | рекомендация по цене с прогнозом: новая цена, ожидаемый объём, маржа, ограничения | § Цены, ценовая стратегия | weekly, monthly |
| `simulate_price_change` | reporter | сценарный прогноз: объём, маржа, выручка при изменении цены на X% | § Цены, ценовая стратегия | weekly, monthly |
| `get_article_economics` | reporter, funnel | юнит-экономика артикулов: profit_per_sale, margin%, DRR, ROMI, CAC | § Юнит-экономика артикулов (Top/Bottom) | weekly, monthly, funnel_weekly |
| `get_marketing_overview` | marketer | маркетинговая сводка: расход, ДРР%, CPO, заказы по каналам, avg_check_order, margin, margin_pct, brand_totals | § Исполнительная сводка, § Анализ по каналам | marketing_weekly, marketing_monthly |
| `get_funnel_analysis` | marketer | анализ рекламной воронки канала: показы → клики → корзина → заказы; CTR, CPC, CPM, CPL, CPO; для WB также органическая воронка | § Анализ воронки | marketing_weekly, marketing_monthly |
| `get_organic_vs_paid` | marketer | органика vs платное WB: доля трафика, конверсии, заказы из органики vs рекламы | § Органика vs Платное | marketing_weekly, marketing_monthly |
| `get_external_ad_breakdown` | marketer | внешняя реклама: блогеры, ВК, креаторы, расход, заказы, ДРР по каждому типу | § Внешняя реклама | marketing_weekly, marketing_monthly |
| `get_campaign_performance` | marketer | эффективность рекламных кампаний: расход, показы, клики, заказы, CTR, CPC | § Дневная динамика рекламы | marketing_weekly, marketing_monthly |
| `get_model_ad_efficiency` | marketer | эффективность рекламы по моделям: расход, заказы, ДРР%, ROMI%, CTR%, CPC | § Эффективность по моделям, § Чёрные дыры рекламы | marketing_weekly, marketing_monthly |
| `get_ad_daily_trend` | marketer | дневная динамика рекламных метрик: расход, показы, клики, CTR, CPC, заказы | § Дневная динамика рекламы | marketing_weekly, marketing_monthly |
| `get_ad_budget_utilization` | marketer | утилизация рекламного бюджета WB: план vs факт, дневное распределение | § Дневная динамика рекламы | marketing_weekly, marketing_monthly |
| `get_ad_spend_correlation` | marketer | корреляция рекламного расхода с заказами и маржой по моделям | § Эффективность по моделям | marketing_monthly |
| `mkt_get_channel_finance` | marketer | финансы канала в маркетинговом контексте (аналог get_channel_finance для маркетера) | § Анализ по каналам | marketing_weekly, marketing_monthly |
| `mkt_get_margin_levers` | marketer | декомпозиция маржи по 5 рычагам в маркетинговом контексте | § Сведение ΔМаржи (Reconciliation) | marketing_monthly |
| `mkt_get_model_breakdown` | marketer | декомпозиция по моделям в маркетинговом контексте | § Эффективность по моделям | marketing_weekly, marketing_monthly |
| `get_model_anomalies` | marketer | аномалии по моделям WB: отклонения >30% по CTR, переходам, корзине, заказам | § Эффективность по моделям | marketing_weekly, marketing_monthly |
| `get_ozon_organic_estimate` | marketer | расчётная органика OZON: organic_orders = total_orders − ad_orders | § Анализ по каналам (OZON) | marketing_weekly, marketing_monthly |
| `get_ad_profitability_alerts` | marketer | алерты убыточной рекламы: модели где ROMI < порога или CAC > прибыли на продажу | § Чёрные дыры рекламы | marketing_weekly, marketing_monthly |
| `get_search_keywords` | marketer, funnel | ключевые слова WB: частотность, переходы, заказы per keyword | § Ключевые слова: генераторы и пустышки | marketing_weekly, marketing_monthly, funnel_weekly |
| `build_funnel_report` | funnel | ПОЛНЫЙ отчёт воронки по всем моделям: данные из базы, форматирование таблиц, гипотезы — в формате telegram_summary + brief_summary + detailed_report | весь отчёт (генерируется в Python, без LLM) | funnel_weekly |
| `get_funnel_overview` | funnel | обзор модели: полная воронка (переходы→выкупы), конверсии CRO/CRP, доля органики, маржа, ДРР WoW | § Обзор модели, § Сквозная конверсия | funnel_weekly |
| `get_article_funnel` | funnel | воронка по артикулам WoW: переходы, корзина, заказы, выкупы, все CR (CRO, CRP) | § Артикулы vs Модель | funnel_weekly |
| `get_article_ad_attribution` | funnel | органика vs реклама per article: доля органического трафика и заказов | § Связь воронки и финансов | funnel_weekly |
| `get_keyword_positions` | funnel | позиции по ключевым словам WoW: medianPosition, frequency, visibility | § Ключевые слова (дополнение) | funnel_weekly |
| `search_knowledge_base` | reporter, marketer, funnel | экспертная база знаний WB (курс, плейбуки, ручные записи): best practices по метрикам, проверенные стратегии | § Гипотезы → действия, § Рекомендации | all |

---

## Секции отчёта → Tools (обратное отображение)

| Секция отчёта | Обязательные tools | Агент |
|---|---|---|
| § Паспорт отчёта | `validate_data_quality` | reporter |
| § Топ-выводы и действия | `get_brand_finance`, `get_margin_levers` | reporter |
| § План-факт | `get_plan_vs_fact` | reporter, marketer |
| § Ключевые изменения (Бренд) | `get_brand_finance` | reporter |
| § Цены, ценовая стратегия и динамика СПП | `get_channel_finance`, `get_margin_levers` | reporter |
| § Сведение ΔМаржи (Reconciliation) | `get_margin_levers`, `get_channel_finance` | reporter |
| § Wildberries (объём, модели, воронка, затраты, реклама) | `get_channel_finance`, `get_model_breakdown`, `get_advertising_stats` | reporter |
| § OZON (объём, модели, затраты, реклама) | `get_channel_finance`, `get_model_breakdown` | reporter |
| § Юнит-экономика артикулов (Top/Bottom) | `get_article_economics` | reporter |
| § Модели — драйверы прибыли (WB) | `get_model_breakdown`, `get_orders_by_model` | reporter |
| § Модели — антидрайверы (WB) | `get_model_breakdown`, `get_orders_by_model` | reporter |
| § Модели — драйверы/антидрайверы (OZON) | `get_model_breakdown`, `get_orders_by_model` | reporter |
| § Гипотезы → действия → метрики контроля | `search_knowledge_base` (опционально) | reporter |
| § Рекомендации Advisor | — (из контекста оркестратора) | orchestrator |
| § Итог | все предыдущие секции | reporter |
| § Исполнительная сводка | `get_marketing_overview` | marketer |
| § Анализ по каналам (маркетинг) | `get_marketing_overview`, `mkt_get_channel_finance` | marketer |
| § Анализ воронки (маркетинг) | `get_funnel_analysis` | marketer |
| § Органика vs Платное | `get_organic_vs_paid` | marketer |
| § Внешняя реклама | `get_external_ad_breakdown` | marketer |
| § Эффективность по моделям (маркетинг) | `get_model_ad_efficiency`, `get_model_anomalies` | marketer |
| § Дневная динамика рекламы | `get_campaign_performance`, `get_ad_daily_trend` | marketer |
| § Средний чек и связь с ДРР | `get_marketing_overview` | marketer |
| § Рекомендации и план действий | `search_knowledge_base` | marketer |
| § Чёрные дыры рекламы | `get_ad_profitability_alerts`, `get_model_ad_efficiency` | marketer |
| § Ключевые слова: генераторы и пустышки | `get_search_keywords` | marketer, funnel |
| Весь funnel отчёт | `build_funnel_report` | funnel |

---

## Зависимости при недоступности инструментов (Phase 3 pre-flight)

| Tool недоступен | Секции под угрозой | Severity |
|---|---|---|
| `get_brand_finance` | § Ключевые изменения (Бренд), § Топ-выводы | CRITICAL — отчёт не может быть сформирован |
| `get_margin_levers` | § Сведение ΔМаржи (Reconciliation) | HIGH — ключевая аналитическая секция |
| `get_plan_vs_fact` | § План-факт | MEDIUM — пропустить секцию если плана нет |
| `get_advertising_stats` | § Воронка продаж WB, § Реклама WB | MEDIUM — заполнить "данные недоступны" |
| `get_model_breakdown` | § Модельная декомпозиция, § Драйверы/Антидрайверы | HIGH — невозможен drill-down |
| `get_article_economics` | § Юнит-экономика артикулов (Top/Bottom) | MEDIUM (только weekly/monthly) |
| `build_funnel_report` | Весь отчёт воронки | CRITICAL — funnel агент не может работать |
| `get_marketing_overview` | § Исполнительная сводка, § Анализ по каналам | CRITICAL (для маркетинговых отчётов) |
| `validate_data_quality` | § Паспорт отчёта (Полнота данных) | LOW — продолжить с предупреждением |

---

*Module: data-map.md | Version: v2.0 | Part of agents/oleg/playbooks/*
*Used by: orchestrator for pre-flight checks (Phase 3)*
