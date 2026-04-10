"""
Regression Engine — статистический движок для ценовой аналитики.

Методы:
- estimate_price_elasticity: ценовая эластичность спроса (log-log OLS)
- margin_factor_regression: многофакторная регрессия маржи
- compute_correlation_matrix: корреляции цена-метрики
- detect_price_trend: тренд цены (Mann-Kendall + MA)
- run_full_analysis: полный анализ модели
"""
import logging

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


def estimate_price_elasticity(
    data: list[dict],
    min_observations: int = 14,
    half_life_days: int = 30,
    min_price_range_pct: float = 0.05,
    min_price_changes: int = 2,
    price_round_step: float = 1.0,
) -> dict:
    """
    Оценка ценовой эластичности спроса.

    Оркестратор: запускает селектор моделей (Linear vs Quadratic) с rolling
    walk-forward бэктестингом на orders_count. Возвращает лучшую валидную модель
    или статус блокировки с reason_code.

    Backward-compatible: ключи elasticity, r_squared, p_value, n_observations,
    quality_metrics, confidence_interval_95 сохранены в корне словаря.

    Args:
        data: список dict с ключами 'date', 'price_per_unit', 'orders_count'
        min_observations: минимум наблюдений для регрессии
        half_life_days: период полураспада для экспоненциального взвешивания
        min_price_range_pct: минимальный диапазон цены (доля от средней)
        min_price_changes: минимальное количество изменений цены
        price_round_step: шаг округления цены для подавления микро-шума

    Returns:
        dict с elasticity, r_squared, p_value, quality_metrics, selected_model,
        backtest_results, selection_status и т.д.
    """
    if len(data) < min_observations:
        return {
            'error': 'insufficient_data',
            'n_observations': len(data),
            'min_required': min_observations,
        }

    df = pd.DataFrame(data)
    # Целевая переменная спроса: prefer orders_count, fallback to sales_count.
    if 'orders_count' in df.columns:
        demand_col = 'orders_count'
    elif 'sales_count' in df.columns:
        demand_col = 'sales_count'
        logger.warning(
            "estimate_price_elasticity: using deprecated fallback demand column sales_count; "
            "prefer orders_count"
        )
    else:
        return {
            'error': 'missing_orders_count',
            'n_observations': len(df),
            'note': (
                'orders_count column is required; '
                'fallback to sales_count is supported only when the column exists'
            ),
        }
    mask = (df['price_per_unit'] > 0) & (df[demand_col] > 0)
    df = df[mask].copy()

    if len(df) < min_observations:
        return {
            'error': 'insufficient_nonzero_data',
            'n_observations': len(df),
            'min_required': min_observations,
        }

    # --- Расчет quality_metrics ---
    prices = df['price_per_unit'].values
    rounded_prices = np.round(prices / price_round_step) * price_round_step

    n_unique_prices = int(len(np.unique(rounded_prices)))
    rp_min, rp_max, rp_mean = float(rounded_prices.min()), float(rounded_prices.max()), float(rounded_prices.mean())
    price_range_pct = (rp_max - rp_min) / rp_mean if rp_mean > 0 else 0.0

    if 'date' in df.columns:
        df_sorted = df.sort_values('date')
        sorted_rounded = np.round(df_sorted['price_per_unit'].values / price_round_step) * price_round_step
    else:
        sorted_rounded = rounded_prices
    n_price_changes = int(np.sum(sorted_rounded[1:] != sorted_rounded[:-1]))

    date_coverage = 1.0
    if 'date' in df.columns:
        dates = pd.to_datetime(df['date']).dt.date
        min_date, max_date = dates.min(), dates.max()
        span_days = (max_date - min_date).days + 1
        date_coverage = len(df) / span_days if span_days > 0 else 1.0

    n_obs = len(df)

    quality_metrics = {
        'n_unique_prices': n_unique_prices,
        'price_range_pct': round(price_range_pct, 4),
        'n_price_changes': n_price_changes,
        'date_coverage': round(date_coverage, 3),
        'insufficient_unique_prices': n_unique_prices < 3,
        'low_price_range': price_range_pct < min_price_range_pct,
        'insufficient_price_changes': n_price_changes < min_price_changes,
        'low_date_coverage': date_coverage < 0.7,
    }
    # --- Конец расчета quality_metrics ---

    # Backward-compatible mode for historical datasets that only have sales_count.
    # Legacy datasets stay on a simpler estimator to preserve historical behavior.
    if demand_col == 'sales_count':
        legacy = _estimate_price_elasticity_legacy_linear(
            data=data,
            min_observations=min_observations,
            half_life_days=half_life_days,
            demand_col=demand_col,
        )
        legacy['quality_metrics'] = quality_metrics
        legacy['selected_model'] = legacy.get('selected_model', 'legacy_linear')
        legacy['selection_status'] = legacy.get('selection_status', 'DEPRECATED_FALLBACK')
        legacy['backtest_results'] = legacy.get('backtest_results', {})
        legacy['demand_column'] = demand_col
        return legacy

    # --- Оркестрация: запуск селектора моделей ---
    selection_result = _select_best_model(
        df=df,
        demand_col=demand_col,
        half_life_days=half_life_days,
        quality_metrics=quality_metrics,
        n_obs=n_obs,
    )

    # Если селектор вернул блокировку — возвращаем с quality_metrics
    if selection_result.get('selection_status') != 'PASS':
        return {
            'error': selection_result.get('reason_code', 'model_selection_failed'),
            'n_observations': n_obs,
            'quality_metrics': quality_metrics,
            'selected_model': 'none',
            'selection_status': selection_result.get('selection_status'),
            'reason_code': selection_result.get('reason_code'),
            'backtest_results': selection_result.get('backtest_results', {}),
        }

    # Возвращаем результат лучшей модели + мета-данные (backward-compatible)
    best = selection_result['best_result']
    best['quality_metrics'] = quality_metrics
    best['demand_column'] = demand_col
    best['selected_model'] = selection_result['selected_model']
    best['selection_status'] = 'PASS'
    best['backtest_results'] = selection_result.get('backtest_results', {})
    return best


def _estimate_price_elasticity_legacy_linear(
    data: list[dict],
    min_observations: int,
    half_life_days: int,
    demand_col: str = 'sales_count',
) -> dict:
    """
    Legacy weighted log-log estimator used for deprecated sales_count fallback.
    """
    df = pd.DataFrame(data)
    mask = (df['price_per_unit'] > 0) & (df[demand_col] > 0)
    df = df[mask].copy()

    if len(df) < min_observations:
        return {
            'error': 'insufficient_nonzero_data',
            'n_observations': len(df),
            'min_required': min_observations,
        }

    log_p = np.log(df['price_per_unit'].values)
    log_q = np.log(df[demand_col].values)

    if 'date' in df.columns:
        dates = pd.to_datetime(df['date'])
        max_date = dates.max()
        days_ago = (max_date - dates).dt.days.values.astype(float)
        weights = np.exp(-np.log(2) * days_ago / half_life_days)
    else:
        weights = np.ones(len(df))

    try:
        import statsmodels.api as sm

        X = sm.add_constant(log_p)
        model = sm.WLS(log_q, X, weights=weights).fit()

        beta = float(model.params[1])
        return {
            'elasticity': round(beta, 3),
            'elasticity_se': round(float(model.bse[1]), 3),
            'r_squared': round(float(model.rsquared), 3),
            'p_value': round(float(model.pvalues[1]), 4),
            'n_observations': len(df),
            'is_significant': float(model.pvalues[1]) < 0.05,
            'interpretation': _interpret_elasticity(beta),
            'confidence_interval_95': [
                round(float(model.conf_int()[1][0]), 3),
                round(float(model.conf_int()[1][1]), 3),
            ],
            'selected_model': 'legacy_linear',
            'selection_status': 'DEPRECATED_FALLBACK',
            'note': 'deprecated_sales_count_fallback',
        }
    except Exception as e:
        logger.error(f"Legacy elasticity estimation failed: {e}")
        slope, _, r_value, p_value, std_err = stats.linregress(log_p, log_q)
        return {
            'elasticity': round(slope, 3),
            'elasticity_se': round(std_err, 3),
            'r_squared': round(r_value ** 2, 3),
            'p_value': round(p_value, 4),
            'n_observations': len(df),
            'is_significant': p_value < 0.05,
            'interpretation': _interpret_elasticity(slope),
            'selected_model': 'legacy_linear',
            'selection_status': 'DEPRECATED_FALLBACK',
            'note': 'fallback_scipy_no_weights_deprecated_sales_count',
        }



def _interpret_elasticity(beta: float) -> str:
    """Интерпретация коэффициента эластичности."""
    abs_beta = abs(beta)
    if abs_beta < 0.5:
        return 'highly_inelastic'
    elif abs_beta < 1.0:
        return 'inelastic'
    elif abs(abs_beta - 1.0) < 0.1:
        return 'unit_elastic'
    elif abs_beta < 2.0:
        return 'elastic'
    else:
        return 'highly_elastic'


def _compute_wape_mae(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """
    Расчет WAPE и MAE.

    WAPE = sum(|actual - predicted|) / sum(|actual|)
    Устойчив к нулям и малым значениям (в отличие от MAPE).
    """
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    abs_errors = np.abs(actual - predicted)
    mae = float(np.mean(abs_errors))
    sum_actual = float(np.sum(np.abs(actual)))
    wape = float(np.sum(abs_errors) / sum_actual) if sum_actual > 1e-10 else 1.0
    return {'mae': mae, 'wape': wape}


def _backtest_single_model(
    df: pd.DataFrame,
    demand_col: str,
    half_life_days: int,
    model_type: str,
    n_windows: int = 3,
    min_train_size: int = 20,
    overfit_ratio_threshold: float = 1.5,
    wape_spread_threshold: float = 0.2,
    wape_soft_limit: float = 0.70,
    baseline_lift_threshold: float = 0.10,
) -> dict:
    """
    Rolling walk-forward бэктестинг для одной модели.

    Для каждого окна:
      - train: [0..t], test: [t+1..t+h]
      - train_error: in-sample (на обучающих данных)
      - test_error: out-of-sample (на отложенных данных)

    Бенчмарки:
      - Naive (t-1): последнее известное значение
      - MA-7: скользящее среднее за 7 дней

    Returns:
        dict с median_test_wape, median_overfit_ratio, is_reliable, reason
    """
    try:
        import statsmodels.api as sm
    except ImportError:
        return {'is_reliable': False, 'reason': 'statsmodels_unavailable'}

    n = len(df)
    # Минимальный размер тренировочного окна + хотя бы 5 точек для теста
    min_total = min_train_size + 5
    if n < min_total:
        return {'is_reliable': False, 'reason': 'insufficient_data_for_backtest'}

    # Определяем точки разреза: равномерно от 60% до 85% данных
    step = max(1, (n - min_train_size - 5) // (n_windows + 1))
    cutpoints = [
        min_train_size + step * (i + 1)
        for i in range(n_windows)
        if min_train_size + step * (i + 1) < n - 3
    ]
    if not cutpoints:
        cutpoints = [n * 2 // 3]

    window_results = []

    for t in cutpoints:
        train_df = df.iloc[:t].copy()
        test_df = df.iloc[t:].copy()

        if len(train_df) < min_train_size or len(test_df) < 3:
            continue

        # Подготовка данных
        train_mask = (train_df['price_per_unit'] > 0) & (train_df[demand_col] > 0)
        test_mask = (test_df['price_per_unit'] > 0) & (test_df[demand_col] > 0)
        train_clean = train_df[train_mask]
        test_clean = test_df[test_mask]

        if len(train_clean) < min_train_size or len(test_clean) < 2:
            continue

        log_p_train = np.log(train_clean['price_per_unit'].values)
        log_q_train = np.log(train_clean[demand_col].values)
        log_p_test = np.log(test_clean['price_per_unit'].values)
        q_test_actual = test_clean[demand_col].values

        # Веса для обучения
        if 'date' in train_clean.columns:
            dates_ts = pd.to_datetime(train_clean['date'])
            max_date_ts = dates_ts.max()
            days_ago = (max_date_ts - dates_ts).dt.days.values.astype(float)
            weights = np.exp(-np.log(2) * days_ago / half_life_days)
        else:
            weights = np.ones(len(train_clean))

        try:
            if model_type == 'linear':
                X_train = sm.add_constant(log_p_train)
                X_test = sm.add_constant(log_p_test)
                n_params = 2
            else:  # quadratic
                X_train = sm.add_constant(np.column_stack([log_p_train, log_p_train ** 2]))
                X_test = sm.add_constant(np.column_stack([log_p_test, log_p_test ** 2]))
                n_params = 3

            maxlags = max(1, int(min(7, len(train_clean) // 5)))
            fitted = sm.WLS(log_q_train, X_train, weights=weights).fit(
                cov_type='HAC', cov_kwds={'maxlags': maxlags}
            )

            # In-sample (train) predictions
            log_q_train_pred = fitted.predict(X_train)
            q_train_pred = np.exp(log_q_train_pred)
            q_train_actual = np.exp(log_q_train)
            train_metrics = _compute_wape_mae(q_train_actual, q_train_pred)

            # Out-of-sample (test) predictions
            log_q_test_pred = fitted.predict(X_test)
            q_test_pred = np.exp(log_q_test_pred)
            test_metrics = _compute_wape_mae(q_test_actual, q_test_pred)

            # Naive baselines на тестовом окне
            # Naive (t-1): последнее значение из трейна
            naive_pred = np.full(len(q_test_actual), np.exp(log_q_train[-1]))
            naive_metrics = _compute_wape_mae(q_test_actual, naive_pred)

            # MA-7: среднее последних 7 значений трейна
            ma7_val = float(np.mean(np.exp(log_q_train[-7:])))
            ma7_pred = np.full(len(q_test_actual), ma7_val)
            ma7_metrics = _compute_wape_mae(q_test_actual, ma7_pred)

            best_baseline_wape = min(naive_metrics['wape'], ma7_metrics['wape'])

            window_results.append({
                'train_mae': train_metrics['mae'],
                'train_wape': train_metrics['wape'],
                'test_mae': test_metrics['mae'],
                'test_wape': test_metrics['wape'],
                'naive_wape': naive_metrics['wape'],
                'ma7_wape': ma7_metrics['wape'],
                'best_baseline_wape': best_baseline_wape,
                'overfit_ratio': test_metrics['mae'] / (train_metrics['mae'] + 1e-10),
                'wape_spread': test_metrics['wape'] - train_metrics['wape'],
                'n_params': n_params,
                'n_obs': len(train_clean),
            })

        except Exception as e:
            logger.warning(f"Backtest window failed ({model_type}): {e}")
            continue

    if not window_results:
        return {'is_reliable': False, 'reason': 'all_windows_failed'}

    # Агрегация: медиана по окнам
    median_test_wape = float(np.median([w['test_wape'] for w in window_results]))
    median_train_wape = float(np.median([w['train_wape'] for w in window_results]))
    median_overfit_ratio = float(np.median([w['overfit_ratio'] for w in window_results]))
    median_wape_spread = float(np.median([w['wape_spread'] for w in window_results]))
    median_best_baseline_wape = float(np.median([w['best_baseline_wape'] for w in window_results]))
    n_params = window_results[0]['n_params']
    n_obs_median = float(np.median([w['n_obs'] for w in window_results]))

    # Complexity penalty score
    lam = 0.5
    score = median_test_wape + lam * (n_params / max(n_obs_median, 1))

    # Проверка критериев блокировки
    reason = None
    if median_overfit_ratio > overfit_ratio_threshold:
        reason = f'overfit_ratio={median_overfit_ratio:.2f} > {overfit_ratio_threshold}'
    elif median_wape_spread > wape_spread_threshold:
        reason = f'wape_spread={median_wape_spread:.2f} > {wape_spread_threshold}'
    elif median_test_wape > wape_soft_limit:
        reason = f'wape={median_test_wape:.2f} > {wape_soft_limit} (soft limit)'
    elif median_best_baseline_wape > 0 and (
        (median_best_baseline_wape - median_test_wape) / median_best_baseline_wape < baseline_lift_threshold
    ):
        reason = (
            f'no_baseline_lift: model_wape={median_test_wape:.2f}, '
            f'baseline_wape={median_best_baseline_wape:.2f} '
            f'(lift < {baseline_lift_threshold:.0%})'
        )

    return {
        'is_reliable': reason is None,
        'reason': reason,
        'score': round(score, 4),
        'median_test_wape': round(median_test_wape, 4),
        'median_train_wape': round(median_train_wape, 4),
        'median_overfit_ratio': round(median_overfit_ratio, 3),
        'median_wape_spread': round(median_wape_spread, 4),
        'median_best_baseline_wape': round(median_best_baseline_wape, 4),
        'n_windows': len(window_results),
        'window_details': window_results,
    }


def _select_best_model(
    df: pd.DataFrame,
    demand_col: str,
    half_life_days: int,
    quality_metrics: dict,
    n_obs: int,
    simplicity_delta: float = 0.01,
) -> dict:
    """
    Strict Pipeline: Sufficiency → Validity → Quality → Score.

    1. Sufficiency: проверяем достаточность данных и вариацию цены.
    2. Validity: отбрасываем модели с положительной эластичностью.
    3. Quality: бэктестинг + сравнение с Naive Baselines.
    4. Score: выбираем лучшую модель; предпочитаем Linear при близких Score.

    Returns:
        dict с selection_status, reason_code, selected_model, best_result, backtest_results
    """
    try:
        import statsmodels.api as sm
    except ImportError:
        return {
            'selection_status': 'FAIL',
            'reason_code': 'statsmodels_unavailable',
        }

    # ── 1. Sufficiency ──────────────────────────────────────────────────────
    if n_obs < 30 or quality_metrics.get('low_date_coverage', False):
        return {
            'selection_status': 'INSUFFICIENT_DATA',
            'reason_code': 'insufficient_data',
        }
    if (
        quality_metrics.get('insufficient_unique_prices', False)
        or quality_metrics.get('low_price_range', False)
        or quality_metrics.get('insufficient_price_changes', False)
    ):
        return {
            'selection_status': 'FAIL',
            'reason_code': 'low_price_variation',
        }

    # ── Обучение обеих моделей на полном датасете (для коэффициентов) ───────
    log_p = np.log(df['price_per_unit'].values)
    log_q = np.log(df[demand_col].values)

    if 'date' in df.columns:
        dates_ts = pd.to_datetime(df['date'])
        max_date_ts = dates_ts.max()
        days_ago = (max_date_ts - dates_ts).dt.days.values.astype(float)
        weights = np.exp(-np.log(2) * days_ago / half_life_days)
    else:
        weights = np.ones(len(df))

    maxlags = max(1, int(min(7, n_obs // 5)))

    candidates = {}  # model_type -> (fit_result_dict, backtest_dict)

    for model_type in ('linear', 'quadratic'):
        try:
            if model_type == 'linear':
                X = sm.add_constant(log_p)
                fitted = sm.WLS(log_q, X, weights=weights).fit(
                    cov_type='HAC', cov_kwds={'maxlags': maxlags}
                )
                beta = float(fitted.params[1])
                fit_result = {
                    'elasticity': round(beta, 3),
                    'elasticity_se': round(float(fitted.bse[1]), 3),
                    'r_squared': round(float(fitted.rsquared), 3),
                    'p_value': round(float(fitted.pvalues[1]), 4),
                    'n_observations': n_obs,
                    'is_significant': float(fitted.pvalues[1]) < 0.05,
                    'interpretation': _interpret_elasticity(beta),
                    'confidence_interval_95': [
                        round(float(fitted.conf_int()[1][0]), 3),
                        round(float(fitted.conf_int()[1][1]), 3),
                    ],
                }
            else:  # quadratic
                log_p_sq = log_p ** 2
                X = sm.add_constant(np.column_stack([log_p, log_p_sq]))
                fitted = sm.WLS(log_q, X, weights=weights).fit(
                    cov_type='HAC', cov_kwds={'maxlags': maxlags}
                )
                b1 = float(fitted.params[1])
                b2 = float(fitted.params[2])
                quadratic_p = float(fitted.pvalues[2])
                is_nonlinear = quadratic_p < 0.05
                optimal_price = None
                if is_nonlinear and abs(b2) > 1e-10:
                    opt_log_p = -b1 / (2 * b2)
                    optimal_price = round(float(np.exp(opt_log_p)), 2)
                fit_result = {
                    'elasticity': round(b1, 3),
                    'elasticity_se': round(float(fitted.bse[1]), 3),
                    'r_squared': round(float(fitted.rsquared), 3),
                    'p_value': round(float(fitted.pvalues[1]), 4),
                    'n_observations': n_obs,
                    'is_significant': float(fitted.pvalues[1]) < 0.05,
                    'interpretation': _interpret_elasticity(b1),
                    'confidence_interval_95': [
                        round(float(fitted.conf_int()[1][0]), 3),
                        round(float(fitted.conf_int()[1][1]), 3),
                    ],
                    'quadratic_term': round(b2, 4),
                    'quadratic_p_value': round(quadratic_p, 4),
                    'is_nonlinear': is_nonlinear,
                    'optimal_price': optimal_price,
                }

            # ── 2. Validity: отбрасываем модели с β > 0 ──────────────────
            if fit_result['elasticity'] > 0:
                logger.info(f"Model '{model_type}' rejected: positive elasticity ({fit_result['elasticity']})")
                continue

            # ── 3. Quality: бэктестинг ────────────────────────────────────
            bt = _backtest_single_model(
                df=df,
                demand_col=demand_col,
                half_life_days=half_life_days,
                model_type=model_type,
            )
            fit_result['is_confounded'] = False

            if bt['is_reliable']:
                candidates[model_type] = (fit_result, bt)
            else:
                logger.info(f"Model '{model_type}' rejected by backtest: {bt.get('reason')}")

        except Exception as e:
            logger.warning(f"Model '{model_type}' failed: {e}")
            continue

    if not candidates:
        return {
            'selection_status': 'FAIL',
            'reason_code': 'low_predictive_power',
            'backtest_results': {},
        }

    # ── 4. Score: выбираем победителя ────────────────────────────────────────
    # Предпочитаем Linear при Score_quad - Score_linear < simplicity_delta
    backtest_results = {k: v[1] for k, v in candidates.items()}

    if 'linear' in candidates and 'quadratic' in candidates:
        score_lin = candidates['linear'][1]['score']
        score_quad = candidates['quadratic'][1]['score']
        if score_quad - score_lin < simplicity_delta:
            winner = 'linear'
        else:
            winner = 'quadratic'
    else:
        winner = next(iter(candidates))

    best_result, best_bt = candidates[winner]

    return {
        'selection_status': 'PASS',
        'selected_model': winner,
        'best_result': best_result,
        'backtest_results': backtest_results,
    }


def margin_factor_regression(data: list[dict]) -> dict:
    """
    Многофакторная регрессия: какие факторы сильнее всего влияют на маржу%.

    margin_pct = b₀ + b₁·price + b₂·spp + b₃·drr + b₄·logistics + b₅·cogs + ε

    Возвращает стандартизированные бета-коэффициенты для сравнения силы влияния.
    """
    if len(data) < 20:
        return {
            'error': 'insufficient_data',
            'n_observations': len(data),
            'min_required': 20,
        }

    df = pd.DataFrame(data)

    # Целевая переменная
    if 'margin_pct' not in df.columns:
        return {'error': 'missing_column_margin_pct'}

    # Предикторы
    predictors = ['price_per_unit', 'spp_pct', 'drr_pct', 'logistics_per_unit', 'cogs_per_unit']
    available = [p for p in predictors if p in df.columns]

    if len(available) < 2:
        return {'error': 'insufficient_predictors', 'available': available}

    # Убрать строки с NaN/None
    df_clean = df[available + ['margin_pct']].dropna()
    if len(df_clean) < 20:
        return {'error': 'insufficient_clean_data', 'n_clean': len(df_clean)}

    try:
        import statsmodels.api as sm

        y = df_clean['margin_pct'].values
        X = df_clean[available].values

        # Стандартизация для сравнения коэффициентов
        X_std = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-10)
        y_std = (y - y.mean()) / (y.std() + 1e-10)

        X_const = sm.add_constant(X_std)
        model = sm.OLS(y_std, X_const).fit()

        factors = {}
        for i, name in enumerate(available):
            idx = i + 1  # +1 для constant
            beta = float(model.params[idx])
            p_value_raw = float(model.pvalues[idx])
            p_value = p_value_raw if np.isfinite(p_value_raw) else 1.0
            factors[name] = {
                'standardized_beta': round(beta, 3),
                'p_value': round(p_value, 4),
                'is_significant': p_value < 0.05,
                'direction': 'positive' if beta > 0 else 'negative',
            }

        # Ранжировать по абсолютному влиянию
        sorted_factors = sorted(
            factors.items(),
            key=lambda x: abs(x[1]['standardized_beta']),
            reverse=True,
        )

        r_squared = float(model.rsquared)
        r_squared_adj = float(model.rsquared_adj)
        f_statistic = float(model.fvalue) if np.isfinite(float(model.fvalue)) else 0.0
        f_p_value = float(model.f_pvalue) if np.isfinite(float(model.f_pvalue)) else 1.0

        if not np.isfinite(r_squared):
            r_squared = 0.0
        if not np.isfinite(r_squared_adj):
            r_squared_adj = 0.0

        return {
            'r_squared': round(r_squared, 3),
            'r_squared_adj': round(r_squared_adj, 3),
            'n_observations': len(df_clean),
            'factors': dict(sorted_factors),
            'strongest_factor': sorted_factors[0][0] if sorted_factors else None,
            'f_statistic': round(f_statistic, 2),
            'f_p_value': round(f_p_value, 4),
        }
    except Exception as e:
        logger.error(f"Factor regression failed: {e}")
        return {'error': str(e)}


def compute_correlation_matrix(
    data: list[dict],
    target: str = 'price_per_unit',
) -> dict:
    """
    Корреляции между ценой и ключевыми метриками.

    Возвращает Pearson и Spearman корреляции с p-value.
    """
    if len(data) < 10:
        return {'error': 'insufficient_data', 'n': len(data)}

    df = pd.DataFrame(data)

    metrics = [
        'margin_pct', 'margin', 'sales_count', 'revenue_before_spp',
        'spp_pct', 'drr_pct', 'logistics_per_unit', 'cogs_per_unit',
        'adv_total',
    ]
    available = [m for m in metrics if m in df.columns]

    if target not in df.columns:
        return {'error': f'target_column_missing: {target}'}

    correlations = {}
    for metric in available:
        # Убрать NaN
        valid = df[[target, metric]].dropna()
        if len(valid) < 5:
            continue

        x = valid[target].values
        y = valid[metric].values

        # Pearson
        pearson_r, pearson_p = stats.pearsonr(x, y)
        # Spearman
        spearman_r, spearman_p = stats.spearmanr(x, y)

        correlations[metric] = {
            'pearson_r': round(float(pearson_r), 3),
            'pearson_p': round(float(pearson_p), 4),
            'spearman_r': round(float(spearman_r), 3),
            'spearman_p': round(float(spearman_p), 4),
            'is_significant': float(pearson_p) < 0.05 or float(spearman_p) < 0.05,
            'strength': _correlation_strength(pearson_r),
        }

    return {
        'target': target,
        'n_observations': len(df),
        'correlations': correlations,
    }


def _correlation_strength(r: float) -> str:
    """Качественная оценка силы корреляции."""
    abs_r = abs(r)
    if abs_r < 0.2:
        return 'negligible'
    elif abs_r < 0.4:
        return 'weak'
    elif abs_r < 0.6:
        return 'moderate'
    elif abs_r < 0.8:
        return 'strong'
    return 'very_strong'


def detect_price_trend(
    data: list[dict],
    price_key: str = 'price_per_unit',
    window: int = 7,
) -> dict:
    """
    Детекция ценового тренда: Mann-Kendall тест + скользящее среднее.

    Returns:
        trend: 'rising', 'falling', 'stable'
        mann_kendall_tau: статистика
        ma_slope: наклон скользящего среднего
    """
    if len(data) < window + 3:
        return {'error': 'insufficient_data', 'n': len(data), 'min_required': window + 3}

    df = pd.DataFrame(data)
    if price_key not in df.columns:
        return {'error': f'missing_column: {price_key}'}

    prices = df[price_key].dropna().values

    if len(prices) < window + 3:
        return {'error': 'insufficient_nonnan_data'}

    # Mann-Kendall тест
    tau, mk_p = stats.kendalltau(np.arange(len(prices)), prices)

    # Скользящее среднее и его наклон
    ma = pd.Series(prices).rolling(window=window, min_periods=1).mean().values
    if len(ma) >= 2:
        ma_slope = (ma[-1] - ma[0]) / len(ma)
        ma_slope_pct = ma_slope / (ma[0] + 1e-10) * 100
    else:
        ma_slope = 0
        ma_slope_pct = 0

    # Определение тренда
    if mk_p < 0.05:
        trend = 'rising' if tau > 0 else 'falling'
    else:
        trend = 'stable'

    # Волатильность (CV — коэффициент вариации)
    cv = float(np.std(prices) / (np.mean(prices) + 1e-10) * 100)

    return {
        'trend': trend,
        'mann_kendall_tau': round(float(tau), 3),
        'mann_kendall_p': round(float(mk_p), 4),
        'is_significant': float(mk_p) < 0.05,
        'ma_slope_per_day': round(float(ma_slope), 2),
        'ma_slope_pct': round(float(ma_slope_pct), 2),
        'current_price': round(float(prices[-1]), 2),
        'period_avg_price': round(float(np.mean(prices)), 2),
        'price_min': round(float(np.min(prices)), 2),
        'price_max': round(float(np.max(prices)), 2),
        'volatility_cv_pct': round(cv, 2),
        'n_observations': len(prices),
    }


def run_full_analysis(
    data: list[dict],
    model_name: str = '',
    channel: str = '',
) -> dict:
    """
    Полный статистический анализ модели: эластичность + факторы + корреляции + тренд.

    Args:
        data: ежедневные данные из get_*_price_margin_daily()
        model_name: имя модели для отчёта
        channel: 'wb' или 'ozon'

    Returns:
        Комплексный отчёт.
    """
    result = {
        'model': model_name,
        'channel': channel,
        'n_days': len(data),
    }

    if len(data) < 7:
        result['error'] = 'insufficient_data'
        return result

    # 1. Ценовая эластичность
    result['elasticity'] = estimate_price_elasticity(data)

    # 2. Факторная регрессия
    result['factor_regression'] = margin_factor_regression(data)

    # 3. Корреляционная матрица
    result['correlations'] = compute_correlation_matrix(data)

    # 4. Ценовой тренд
    result['price_trend'] = detect_price_trend(data)

    # 5. Тренд маржи
    result['margin_trend'] = detect_price_trend(data, price_key='margin_pct')

    # 6. Базовые статистики
    df = pd.DataFrame(data)
    if 'price_per_unit' in df.columns and 'margin_pct' in df.columns:
        result['summary'] = {
            'avg_price': round(float(df['price_per_unit'].mean()), 2),
            'avg_margin_pct': round(float(df['margin_pct'].mean()), 2),
            'avg_daily_sales': round(float(df['sales_count'].mean()), 1),
            'total_margin': round(float(df['margin'].sum()), 0) if 'margin' in df.columns else None,
            'avg_spp_pct': round(float(df['spp_pct'].mean()), 2) if 'spp_pct' in df.columns else None,
            'avg_drr_pct': round(float(df['drr_pct'].mean()), 2) if 'drr_pct' in df.columns else None,
        }

    return result


def estimate_price_elasticity_quadratic(
    data: list[dict],
    min_observations: int = 20,
    half_life_days: int = 30,
) -> dict:
    """
    Оценка ценовой эластичности с квадратичным членом (нелинейная модель).

    ln(Q) = α + β₁·ln(P) + β₂·ln(P)² + ε

    Позволяет обнаружить нелинейные зависимости: например, оптимальную
    ценовую точку (вершину параболы), где спрос максимален.

    Args:
        data: список dict с ключами 'date', 'price_per_unit', 'sales_count'
        min_observations: минимум наблюдений для регрессии
        half_life_days: период полураспада для экспоненциального взвешивания

    Returns:
        dict с elasticity, quadratic_term, is_nonlinear, optimal_log_price и т.д.
    """
    if len(data) < min_observations:
        return {
            'error': 'insufficient_data',
            'n_observations': len(data),
            'min_required': min_observations,
        }

    df = pd.DataFrame(data)
    mask = (df['price_per_unit'] > 0) & (df['sales_count'] > 0)
    df = df[mask].copy()

    if len(df) < min_observations:
        return {
            'error': 'insufficient_nonzero_data',
            'n_observations': len(df),
            'min_required': min_observations,
        }

    log_p = np.log(df['price_per_unit'].values)
    log_q = np.log(df['sales_count'].values)
    log_p_sq = log_p ** 2

    # Экспоненциальные веса (свежие данные важнее)
    if 'date' in df.columns:
        dates = pd.to_datetime(df['date'])
        max_date = dates.max()
        days_ago = (max_date - dates).dt.days.values.astype(float)
        weights = np.exp(-np.log(2) * days_ago / half_life_days)
    else:
        weights = np.ones(len(df))

    # Линейная модель для сравнения R²
    linear_r_squared = None
    try:
        import statsmodels.api as sm

        X_lin = sm.add_constant(log_p)
        model_lin = sm.WLS(log_q, X_lin, weights=weights).fit()
        linear_r_squared = round(float(model_lin.rsquared), 3)
    except Exception as e:
        logger.warning(f"Linear baseline model failed: {e}")

    # Квадратичная модель: ln(Q) = α + β₁·ln(P) + β₂·ln(P)² + ε
    try:
        import statsmodels.api as sm

        X_quad = sm.add_constant(np.column_stack([log_p, log_p_sq]))
        model_quad = sm.WLS(log_q, X_quad, weights=weights).fit()

        b1 = float(model_quad.params[1])
        b2 = float(model_quad.params[2])
        quadratic_p = float(model_quad.pvalues[2])
        is_nonlinear = quadratic_p < 0.05

        # Оптимальная цена (вершина параболы): d(ln Q)/d(ln P) = b1 + 2*b2*ln(P) = 0
        optimal_log_price = None
        optimal_price = None
        if is_nonlinear and abs(b2) > 1e-10:
            optimal_log_price = round(-b1 / (2 * b2), 4)
            optimal_price = round(float(np.exp(optimal_log_price)), 2)

        return {
            'elasticity': round(b1, 3),
            'elasticity_se': round(float(model_quad.bse[1]), 3),
            'quadratic_term': round(b2, 4),
            'quadratic_se': round(float(model_quad.bse[2]), 4),
            'quadratic_p_value': round(quadratic_p, 4),
            'is_nonlinear': is_nonlinear,
            'optimal_log_price': optimal_log_price,
            'optimal_price': optimal_price,
            'linear_r_squared': linear_r_squared,
            'quadratic_r_squared': round(float(model_quad.rsquared), 3),
            'r_squared': round(float(model_quad.rsquared), 3),
            'p_value': round(float(model_quad.pvalues[1]), 4),
            'n_observations': int(mask.sum()),
            'is_significant': float(model_quad.pvalues[1]) < 0.05,
            'interpretation': _interpret_elasticity(b1),
            'confidence_interval_95': [
                round(float(model_quad.conf_int()[1][0]), 3),
                round(float(model_quad.conf_int()[1][1]), 3),
            ],
        }
    except Exception as e:
        logger.error(f"Quadratic elasticity estimation failed: {e}")
        # Fallback: scipy linregress (линейная модель без весов)
        slope, intercept, r_value, p_value, std_err = stats.linregress(log_p, log_q)
        return {
            'elasticity': round(slope, 3),
            'elasticity_se': round(std_err, 3),
            'quadratic_term': None,
            'quadratic_se': None,
            'quadratic_p_value': None,
            'is_nonlinear': False,
            'optimal_log_price': None,
            'optimal_price': None,
            'linear_r_squared': round(r_value ** 2, 3),
            'quadratic_r_squared': None,
            'r_squared': round(r_value ** 2, 3),
            'p_value': round(p_value, 4),
            'n_observations': len(df),
            'is_significant': p_value < 0.05,
            'interpretation': _interpret_elasticity(slope),
            'note': 'fallback_scipy_linear_no_weights',
        }


def estimate_ad_elasticity(
    data: list[dict],
    min_observations: int = 14,
    half_life_days: int = 30,
) -> dict:
    """
    Оценка эластичности спроса по рекламным расходам с контролем цены.

    ln(sales) = α + β·ln(adv) + γ·ln(price) + ε

    β — эластичность по рекламе (ожидание: 0.05–0.5)
    γ — ценовая эластичность (контрольная переменная)

    Args:
        data: список dict с 'date', 'price_per_unit', 'sales_count', 'adv_total'
        min_observations: минимум наблюдений
        half_life_days: период полураспада для экспоненциального взвешивания

    Returns:
        dict с ad_elasticity, price_elasticity, ad_r_squared, p-values и т.д.
    """
    if len(data) < min_observations:
        return {
            'error': 'insufficient_data',
            'n_observations': len(data),
            'min_required': min_observations,
        }

    df = pd.DataFrame(data)

    if 'adv_total' not in df.columns:
        return {'error': 'missing_column_adv_total'}

    # Фильтр: price > 0, sales > 0, adv > 0
    mask = (
        (df['price_per_unit'] > 0)
        & (df['sales_count'] > 0)
        & (df['adv_total'] > 0)
    )
    df = df[mask].copy()

    if len(df) < min_observations:
        return {
            'error': 'insufficient_positive_data',
            'n_observations': len(df),
            'min_required': min_observations,
        }

    log_sales = np.log(df['sales_count'].values)
    log_adv = np.log(df['adv_total'].values)
    log_price = np.log(df['price_per_unit'].values)

    # Экспоненциальные веса (свежие данные важнее)
    if 'date' in df.columns:
        dates = pd.to_datetime(df['date'])
        max_date = dates.max()
        days_ago = (max_date - dates).dt.days.values.astype(float)
        weights = np.exp(-np.log(2) * days_ago / half_life_days)
    else:
        weights = np.ones(len(df))

    # WLS: ln(sales) = α + β·ln(adv) + γ·ln(price)
    try:
        import statsmodels.api as sm

        X = sm.add_constant(np.column_stack([log_adv, log_price]))
        model = sm.WLS(log_sales, X, weights=weights).fit()

        ad_beta = float(model.params[1])
        price_beta = float(model.params[2])

        return {
            'ad_elasticity': round(ad_beta, 3),
            'ad_elasticity_se': round(float(model.bse[1]), 3),
            'ad_p_value': round(float(model.pvalues[1]), 4),
            'price_elasticity': round(price_beta, 3),
            'price_elasticity_se': round(float(model.bse[2]), 3),
            'price_p_value': round(float(model.pvalues[2]), 4),
            'ad_r_squared': round(float(model.rsquared), 3),
            'r_squared_adj': round(float(model.rsquared_adj), 3),
            'n_observations': int(mask.sum()),
            'ad_is_significant': float(model.pvalues[1]) < 0.05,
            'price_is_significant': float(model.pvalues[2]) < 0.05,
            'ad_confidence_interval_95': [
                round(float(model.conf_int()[1][0]), 3),
                round(float(model.conf_int()[1][1]), 3),
            ],
        }
    except Exception as e:
        logger.error(f"Ad elasticity estimation failed: {e}")
        # Fallback: scipy — простая регрессия ln(sales) ~ ln(adv) без контроля цены
        slope, intercept, r_value, p_value, std_err = stats.linregress(log_adv, log_sales)
        return {
            'ad_elasticity': round(slope, 3),
            'ad_elasticity_se': round(std_err, 3),
            'ad_p_value': round(p_value, 4),
            'price_elasticity': None,
            'price_elasticity_se': None,
            'price_p_value': None,
            'ad_r_squared': round(r_value ** 2, 3),
            'r_squared_adj': None,
            'n_observations': len(df),
            'ad_is_significant': p_value < 0.05,
            'price_is_significant': None,
            'note': 'fallback_scipy_no_price_control',
        }


def multi_factor_margin_drivers(
    data: list[dict],
    include_seasonality: bool = True,
    include_interactions: bool = True,
    include_lags: bool = True,
) -> dict:
    """
    Расширенная многофакторная регрессия маржи с сезонными контролями,
    взаимодействиями и лагами.

    Добавляет к margin_factor_regression():
    - Сезонные дамми-переменные (месяц, день недели)
    - Взаимодействия: цена × реклама, цена × СПП
    - Лаги: реклама t-1 (отложенный эффект рекламы)
    - VIF (Variance Inflation Factor) для каждого предиктора
    - AIC/BIC для сравнения моделей

    Returns:
        dict с ключами:
        - factors: list of {name, beta_std, p_value, vif, interpretation}
        - r_squared, adj_r_squared
        - aic, bic
        - n_observations
        - model_comparison: {base_r2, extended_r2, improvement}
        - seasonality: {significant_months, day_of_week_effect}
    """
    if len(data) < 20:
        return {
            'error': 'insufficient_data',
            'n_observations': len(data),
            'min_required': 20,
        }

    df = pd.DataFrame(data)

    # Целевая переменная
    if 'margin_pct' not in df.columns:
        return {'error': 'missing_column_margin_pct'}

    # Базовые предикторы (те же, что в margin_factor_regression)
    base_predictors = ['price_per_unit', 'spp_pct', 'drr_pct', 'logistics_per_unit', 'cogs_per_unit']
    available = [p for p in base_predictors if p in df.columns]

    if len(available) < 2:
        return {'error': 'insufficient_predictors', 'available': available}

    # Убрать строки с NaN/None в базовых столбцах
    df_clean = df[available + ['margin_pct']].copy()
    if 'date' in df.columns:
        df_clean['date'] = pd.to_datetime(df['date'])
    df_clean = df_clean.dropna(subset=available + ['margin_pct'])

    if len(df_clean) < 20:
        return {'error': 'insufficient_clean_data', 'n_clean': len(df_clean)}

    # --- Базовая модель (для сравнения) ---
    try:
        import statsmodels.api as sm
    except ImportError:
        return {'error': 'statsmodels_unavailable'}

    y = df_clean['margin_pct'].values
    X_base = df_clean[available].values

    # Стандартизация базовых предикторов
    base_means = X_base.mean(axis=0)
    base_stds = X_base.std(axis=0) + 1e-10
    X_base_std = (X_base - base_means) / base_stds
    y_mean = y.mean()
    y_std = y.std() + 1e-10
    y_std_vals = (y - y_mean) / y_std

    try:
        X_base_const = sm.add_constant(X_base_std)
        base_model = sm.OLS(y_std_vals, X_base_const).fit()
        base_r2 = float(base_model.rsquared)
    except Exception as e:
        logger.error(f"Base model failed in multi_factor_margin_drivers: {e}")
        return {'error': str(e)}

    # --- Расширенные признаки ---
    extended_names = list(available)
    extended_cols = [df_clean[col].values for col in available]

    # Сезонные дамми-переменные
    seasonal_month_names = []
    seasonal_dow_names = []
    if include_seasonality and 'date' in df_clean.columns:
        dates = df_clean['date']
        months = dates.dt.month.values
        dow = dates.dt.dayofweek.values  # 0=Monday .. 6=Sunday

        # Месяц: дамми-кодирование (drop_first для избежания мультиколлинеарности)
        unique_months = sorted(set(months))
        if len(unique_months) > 1:
            for m in unique_months[1:]:  # drop first month
                col_name = f'month_{m}'
                extended_names.append(col_name)
                seasonal_month_names.append(col_name)
                extended_cols.append((months == m).astype(float))

        # День недели: дамми-кодирование (drop_first)
        unique_dow = sorted(set(dow))
        if len(unique_dow) > 1:
            for d in unique_dow[1:]:  # drop first day
                col_name = f'dow_{d}'
                extended_names.append(col_name)
                seasonal_dow_names.append(col_name)
                extended_cols.append((dow == d).astype(float))

    # Взаимодействия
    interaction_names = []
    if include_interactions:
        if 'price_per_unit' in df_clean.columns and 'drr_pct' in df_clean.columns:
            col_name = 'price_x_drr'
            extended_names.append(col_name)
            interaction_names.append(col_name)
            extended_cols.append(
                df_clean['price_per_unit'].values * df_clean['drr_pct'].values
            )
        if 'price_per_unit' in df_clean.columns and 'spp_pct' in df_clean.columns:
            col_name = 'price_x_spp'
            extended_names.append(col_name)
            interaction_names.append(col_name)
            extended_cols.append(
                df_clean['price_per_unit'].values * df_clean['spp_pct'].values
            )

    # Лаги
    lag_names = []
    if include_lags and 'drr_pct' in df_clean.columns:
        drr_lag1 = np.roll(df_clean['drr_pct'].values, 1)
        drr_lag1[0] = 0.0  # fill first value
        col_name = 'drr_lag1'
        extended_names.append(col_name)
        lag_names.append(col_name)
        extended_cols.append(drr_lag1)

    # Собираем расширенную матрицу
    X_ext = np.column_stack(extended_cols)

    # Стандартизация расширенных предикторов
    ext_means = X_ext.mean(axis=0)
    ext_stds = X_ext.std(axis=0) + 1e-10
    X_ext_std = (X_ext - ext_means) / ext_stds

    try:
        X_ext_const = sm.add_constant(X_ext_std)
        ext_model = sm.OLS(y_std_vals, X_ext_const).fit()
    except Exception as e:
        logger.error(f"Extended model failed in multi_factor_margin_drivers: {e}")
        return {'error': str(e)}

    ext_r2 = float(ext_model.rsquared)
    ext_adj_r2 = float(ext_model.rsquared_adj)
    ext_aic = float(ext_model.aic)
    ext_bic = float(ext_model.bic)

    # --- VIF для каждого предиктора ---
    n_predictors = X_ext_std.shape[1]
    vif_values = []
    for j in range(n_predictors):
        # Регрессируем предиктор j на все остальные
        y_j = X_ext_std[:, j]
        X_others = np.delete(X_ext_std, j, axis=1)
        if X_others.shape[1] == 0:
            vif_values.append(1.0)
            continue
        X_others_const = sm.add_constant(X_others)
        try:
            vif_model = sm.OLS(y_j, X_others_const).fit()
            r2_j = float(vif_model.rsquared)
            vif_j = 1.0 / (1.0 - r2_j) if r2_j < 1.0 else float('inf')
        except Exception:
            vif_j = float('nan')
        vif_values.append(round(vif_j, 2))

    # --- Формируем результат по факторам ---
    factors = []
    for i, name in enumerate(extended_names):
        idx = i + 1  # +1 для constant
        beta = float(ext_model.params[idx])
        p_value_raw = float(ext_model.pvalues[idx])
        p_value = p_value_raw if np.isfinite(p_value_raw) else 1.0
        abs_beta = abs(beta)

        if abs_beta > 0.5:
            interpretation = 'strong_driver'
        elif abs_beta > 0.2:
            interpretation = 'moderate_driver'
        elif abs_beta > 0.05:
            interpretation = 'weak_driver'
        else:
            interpretation = 'negligible'

        factors.append({
            'name': name,
            'beta_std': round(beta, 3),
            'p_value': round(p_value, 4),
            'vif': vif_values[i],
            'is_significant': p_value < 0.05,
            'direction': 'positive' if beta > 0 else 'negative',
            'interpretation': interpretation,
        })

    # Сортируем по абсолютному значению бета (сильнейшие первыми)
    factors.sort(key=lambda x: abs(x['beta_std']), reverse=True)

    # --- Сезонность ---
    seasonality = {'significant_months': [], 'day_of_week_effect': False}
    if include_seasonality:
        for f in factors:
            if f['name'] in seasonal_month_names and f['is_significant']:
                seasonality['significant_months'].append(f['name'])
            if f['name'] in seasonal_dow_names and f['is_significant']:
                seasonality['day_of_week_effect'] = True

    # --- Model comparison ---
    improvement = ext_r2 - base_r2

    return {
        'factors': factors,
        'r_squared': round(ext_r2, 3) if np.isfinite(ext_r2) else 0.0,
        'adj_r_squared': round(ext_adj_r2, 3) if np.isfinite(ext_adj_r2) else 0.0,
        'aic': round(ext_aic, 2) if np.isfinite(ext_aic) else None,
        'bic': round(ext_bic, 2) if np.isfinite(ext_bic) else None,
        'n_observations': len(df_clean),
        'model_comparison': {
            'base_r2': round(base_r2, 3) if np.isfinite(base_r2) else 0.0,
            'extended_r2': round(ext_r2, 3) if np.isfinite(ext_r2) else 0.0,
            'improvement': round(improvement, 3) if np.isfinite(improvement) else 0.0,
        },
        'seasonality': seasonality,
    }


def classify_elastic_policy(
    elasticity: float,
    margin_pct: float,
    turnover_days: float,
    is_phasing_out: bool = False,
) -> dict:
    """
    Классифицирует оптимальную ценовую политику на основе
    эластичности, маржи и оборачиваемости.

    Args:
        elasticity: ценовая эластичность спроса
        margin_pct: маржинальность, %
        turnover_days: оборачиваемость, дней
        is_phasing_out: модель со статусом "Выводим" (распродажа остатков)

    Returns:
        dict с ключами:
        - policy: str
        - action: str ('hold' | 'increase' | 'decrease')
        - reasoning: str
        - priority: str ('high' | 'medium' | 'low')
        - expected_impact: str
    """
    abs_e = abs(elasticity)

    # Модель выводится — особая логика
    if is_phasing_out:
        if margin_pct > 20:
            return {
                'policy': 'controlled_exit',
                'action': 'hold',
                'reasoning': (
                    f'Модель выводится из ассортимента. Маржа {margin_pct:.1f}% > 20% — '
                    f'достаточная для планового вывода. Оборачиваемость {turnover_days:.0f} дн. — '
                    f'это нормально для выводимой модели, остатки распродаются планово.'
                ),
                'priority': 'low',
                'expected_impact': (
                    'Плановая распродажа остатков с сохранением маржи. '
                    'Агрессивное снижение цены не требуется.'
                ),
            }
        else:
            return {
                'policy': 'controlled_exit',
                'action': 'decrease',
                'reasoning': (
                    f'Модель выводится из ассортимента. Маржа {margin_pct:.1f}% < 20% — '
                    f'низкая, но модель всё равно нужно распродать. '
                    f'Умеренное снижение цены для ускорения вывода остатков.'
                ),
                'priority': 'medium',
                'expected_impact': (
                    'Ускорение вывода остатков и высвобождение оборотного капитала.'
                ),
            }

    # clearance — проверяем первым: оборачиваемость > 90 дней — критично
    if turnover_days > 90:
        return {
            'policy': 'clearance',
            'action': 'decrease',
            'reasoning': (
                f'Оборачиваемость {turnover_days:.0f} дней > 90 — замороженный капитал. '
                f'Необходимо снижение цены для ускорения оборота независимо от эластичности.'
            ),
            'priority': 'high',
            'expected_impact': (
                'Ускорение оборота, высвобождение складских остатков и оборотного капитала.'
            ),
        }

    # premium_hold — неэластичный спрос, высокая маржа, быстрый оборот
    if abs_e < 1.0 and margin_pct > 30 and turnover_days < 45:
        return {
            'policy': 'premium_hold',
            'action': 'hold',
            'reasoning': (
                f'Неэластичный спрос (|e|={abs_e:.2f}), маржа {margin_pct:.1f}% > 30%, '
                f'оборачиваемость {turnover_days:.0f} дн < 45. '
                f'Товар продаётся стабильно по текущей цене — менять незачем.'
            ),
            'priority': 'low',
            'expected_impact': (
                'Сохранение текущей прибыльности без риска потери объёма.'
            ),
        }

    # volume_play — эластичный спрос, хорошая маржа, медленный оборот
    if abs_e > 1.0 and margin_pct > 25 and turnover_days > 60:
        return {
            'policy': 'volume_play',
            'action': 'decrease',
            'reasoning': (
                f'Эластичный спрос (|e|={abs_e:.2f}), маржа {margin_pct:.1f}% > 25% (есть запас), '
                f'оборачиваемость {turnover_days:.0f} дн > 60 — замороженный капитал. '
                f'Снижение цены ускорит продажи и компенсирует потерю маржи объёмом.'
            ),
            'priority': 'high',
            'expected_impact': (
                'Рост объёма продаж, ускорение оборачиваемости, '
                'потенциальный рост общей прибыли за счёт оборота.'
            ),
        }

    # margin_squeeze — неэластичный спрос, низкая маржа
    if abs_e < 1.0 and margin_pct < 25:
        return {
            'policy': 'margin_squeeze',
            'action': 'increase',
            'reasoning': (
                f'Неэластичный спрос (|e|={abs_e:.2f}) — повышение цены слабо снизит объём. '
                f'Маржа {margin_pct:.1f}% < 25% — есть потенциал для роста. '
                f'Повышение цены увеличит маржу без существенной потери продаж.'
            ),
            'priority': 'high',
            'expected_impact': (
                'Рост маржинальности при минимальном снижении объёма продаж.'
            ),
        }

    # neutral — всё остальное
    return {
        'policy': 'neutral',
        'action': 'hold',
        'reasoning': (
            f'Эластичность |e|={abs_e:.2f}, маржа {margin_pct:.1f}%, '
            f'оборачиваемость {turnover_days:.0f} дн — нет однозначного сигнала. '
            f'Рекомендуется сохранить текущую цену и мониторить динамику.'
        ),
        'priority': 'medium',
        'expected_impact': (
            'Стабильность текущих показателей; пересмотр при изменении условий.'
        ),
    }
