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
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


def estimate_price_elasticity(
    data: list[dict],
    min_observations: int = 14,
    half_life_days: int = 30,
) -> dict:
    """
    Оценка ценовой эластичности спроса через log-log OLS регрессию.

    ln(Q) = α + β·ln(P) + ε
    β = эластичность (ожидание: от -0.3 до -4.0 для fashion)

    Args:
        data: список dict с ключами 'date', 'price_per_unit', 'sales_count'
        min_observations: минимум наблюдений для регрессии
        half_life_days: период полураспада для экспоненциального взвешивания

    Returns:
        dict с elasticity, r_squared, p_value, is_significant, interpretation
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

    # Экспоненциальные веса (свежие данные важнее)
    if 'date' in df.columns:
        dates = pd.to_datetime(df['date'])
        max_date = dates.max()
        days_ago = (max_date - dates).dt.days.values.astype(float)
        weights = np.exp(-np.log(2) * days_ago / half_life_days)
    else:
        weights = np.ones(len(df))

    # Взвешенная OLS: ln(Q) = α + β·ln(P)
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
            'n_observations': int(mask.sum()),
            'is_significant': float(model.pvalues[1]) < 0.05,
            'interpretation': _interpret_elasticity(beta),
            'confidence_interval_95': [
                round(float(model.conf_int()[1][0]), 3),
                round(float(model.conf_int()[1][1]), 3),
            ],
        }
    except Exception as e:
        logger.error(f"Elasticity estimation failed: {e}")
        # Fallback: scipy linregress (без весов)
        slope, intercept, r_value, p_value, std_err = stats.linregress(log_p, log_q)
        return {
            'elasticity': round(slope, 3),
            'elasticity_se': round(std_err, 3),
            'r_squared': round(r_value ** 2, 3),
            'p_value': round(p_value, 4),
            'n_observations': len(df),
            'is_significant': p_value < 0.05,
            'interpretation': _interpret_elasticity(slope),
            'note': 'fallback_scipy_no_weights',
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
            factors[name] = {
                'standardized_beta': round(float(model.params[idx]), 3),
                'p_value': round(float(model.pvalues[idx]), 4),
                'is_significant': float(model.pvalues[idx]) < 0.05,
                'direction': 'positive' if model.params[idx] > 0 else 'negative',
            }

        # Ранжировать по абсолютному влиянию
        sorted_factors = sorted(
            factors.items(),
            key=lambda x: abs(x[1]['standardized_beta']),
            reverse=True,
        )

        return {
            'r_squared': round(float(model.rsquared), 3),
            'r_squared_adj': round(float(model.rsquared_adj), 3),
            'n_observations': len(df_clean),
            'factors': dict(sorted_factors),
            'strongest_factor': sorted_factors[0][0] if sorted_factors else None,
            'f_statistic': round(float(model.fvalue), 2),
            'f_p_value': round(float(model.f_pvalue), 4),
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
