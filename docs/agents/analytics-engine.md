# Analytics Engine

## Scope

Аналитический контур проекта сейчас состоит из:

- сервисов в `agents/oleg/services/price_analysis/`
- ETL-данных из `services/marketplace_etl/`
- CLI скриптов в `scripts/`:
  - `abc_analysis.py`
  - `abc_analysis_unified.py`
  - `notion_sync.py`
  - `wb_vuki_ratings.py`

Legacy-скрипты `daily_analytics.py`, `period_analytics.py`, `monthly_analytics.py` удалены из активного runtime.

## Ключевые блоки

- Regression/elasticity: `agents/oleg/services/price_analysis/regression_engine.py`
- Deep Elasticity: `agents/oleg/services/price_analysis/deep_elasticity_service.py` (поартикульный анализ, сегментация по ролям, First-Sale Alignment)
- Scenarios/recommendations: `agents/oleg/services/price_analysis/scenario_modeler.py`, `agents/oleg/services/price_analysis/recommendation_engine.py`
- ROI/stock optimization: `agents/oleg/services/price_analysis/roi_optimizer.py`, `agents/oleg/services/price_analysis/stock_price_optimizer.py`

## Проверка качества

```bash
python -m pytest -q
python -m pytest -q services/marketplace_etl/tests
python -m compileall -q agents services shared scripts
```

## Связанные документы

- [telegram-bot.md](telegram-bot.md)
- [../database/DB_METRICS_GUIDE.md](../database/DB_METRICS_GUIDE.md)
- [../database/DATA_QUALITY_NOTES.md](../database/DATA_QUALITY_NOTES.md)
