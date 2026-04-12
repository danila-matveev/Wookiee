<important if="writing SQL queries, GROUP BY, or aggregating data by model/article">
GROUP BY по модели — ВСЕГДА с LOWER(): `LOWER(SPLIT_PART(article, '/', 1))`.
В БД артикулы с разным регистром ("wendy" и "Wendy") — без LOWER() они попадут в разные группы и исказят суммы на десятки процентов.
</important>

<important if="calculating percentage metrics across channels (WB+OZON) or aggregating percentages">
Процентные метрики при объединении каналов — ТОЛЬКО средневзвешенные.
Нельзя просто сложить проценты или присвоить 0.
Формула: `sum(spp_amount) / sum(revenue) * 100`.
</important>

<important if="comparing current vs previous period values">
Все значения для сравниваемого периода должны реально вычисляться и отображаться.
Не хардкодить "—" — всегда считать и хранить both current и previous.
</important>

- Все DB-запросы и утилиты — только `shared/data_layer.py` (shim: `scripts/data_layer.py`). Не дублировать в других скриптах.
- Трафик (`content_analysis`): расхождение ~20% с PowerBI. Фильтры не выяснены. См. `docs/database/DATA_QUALITY_NOTES.md`.
- При обнаружении новых проблем качества данных — фиксировать в `docs/database/DATA_QUALITY_NOTES.md`.
