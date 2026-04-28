# scripts/familia_eval/

Familia Evaluation Pipeline — оценка финансовой целесообразности захода на маркетплейс «Фамилия» (стоковый ритейл).

Один из разовых evaluation-проектов — НЕ скилл, отдельная бизнес-задача. Считает unit-экономику по нескольким сценариям контрактов, прогоняет результаты через LLM-аналитику, выводит recommendation brief.

## Точка входа
```
python scripts/familia_eval/run.py                  # Full pipeline
python scripts/familia_eval/run.py --calc-only      # Data + calc, no LLM
python scripts/familia_eval/run.py --llm-only       # Reuse cached scenarios.json
python scripts/familia_eval/run.py --logistics 80   # Override logistics cost
```

## Содержимое
- `run.py` — оркестратор
- `collector.py` — сбор данных по моделям
- `calculator.py` — расчёт сценариев
- `agents/` — LLM-аналитики по аспектам (финансы, риски, операции)
- `prompts/` — system-промпты агентов
- `config.py` — параметры контрактов и цен

## Owner
danila-matveev
