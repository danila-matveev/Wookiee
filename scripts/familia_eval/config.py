# scripts/familia_eval/config.py
"""Configuration for Familia evaluation pipeline."""

CONFIG = {
    # --- Расходы на единицу ---
    "logistics_to_rc": 65,        # руб/шт доставка Москва → РЦ Бритово
    "packaging_cost": 20,         # руб/шт (гофрокороба, ярлыки, стрейч, паллеты)
    "loss_reserve_pct": 0.05,     # 5% резерв на потери/расхождения при приёмке
    "annual_rate": 0.18,          # стоимость денег (ключевая ставка ЦБ)
    "payment_delay_days": 90,     # отсрочка оплаты Familia

    # --- Сценарии скидок ---
    "discount_range": [0.40, 0.45, 0.50, 0.55, 0.60, 0.65],

    # --- Фильтры артикулов ---
    "min_stock_moysklad": 10,     # мин. остаток на складе для анализа
    "status_filter": ["Выводим", "Архив"],

    # --- LLM модели (OpenRouter) ---
    "model_main": "google/gemini-2.5-flash-preview",
    "model_heavy": "anthropic/claude-sonnet-4-6",

    # --- Период для расчёта метрик МП (последние N дней) ---
    "lookback_days": 30,
}
