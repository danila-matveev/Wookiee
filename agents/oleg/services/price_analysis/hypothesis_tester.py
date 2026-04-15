"""
Hypothesis Tester — тестирование 14 статистических гипотез о ценовых зависимостях.

Модуль проверяет гипотезы по 7 группам:
- H1a-H1c: эластичность спроса (различия между моделями, артикулами, нелинейность)
- H2a-H2b: прибыль и маржинальность (оптимальная цена, влияние СПП)
- H3a-H3b: реклама (убывающая отдача, различия между моделями)
- H4a-H4b: запасы (низкий сток снижает продажи, высокий — сигнал к снижению цены)
- H5a: кросс-модельные эффекты (каннибализация)
- H6a-H6b: временные паттерны (сезонность эластичности, день недели)
- H7a-H7b: ROI (ранжирование, оптимальная цена для ROI vs маржи)

Использует regression_engine.py для повторного использования моделей и
roi_optimizer.py для расчёта ROI.
"""
import logging
from agents.oleg.services.time_utils import get_now_msk
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Минимальные пороги для анализа
MIN_OBSERVATIONS = 14
MIN_GROUPS = 3
MIN_DAYS_SEASONAL = 90


def _make_result(
    hypothesis: str,
    result: str,
    p_value: Optional[float],
    n_observations: int,
    details: dict,
) -> dict:
    """Формирует стандартный dict результата для гипотезы."""
    return {
        'hypothesis': hypothesis,
        'result': result,
        'p_value': round(p_value, 4) if p_value is not None else None,
        'n_observations': n_observations,
        'details': details,
    }


def _safe_log_log_regression(prices: np.ndarray, quantities: np.ndarray) -> Optional[dict]:
    """
    Безопасная log-log регрессия: ln(Q) = alpha + beta * ln(P).

    Возвращает dict с beta, intercept, r_squared, p_value, residuals или None при ошибке.
    """
    mask = (prices > 0) & (quantities > 0)
    p = prices[mask]
    q = quantities[mask]
    if len(p) < MIN_OBSERVATIONS:
        return None
    log_p = np.log(p)
    log_q = np.log(q)
    try:
        slope, intercept, r_value, p_value, std_err = stats.linregress(log_p, log_q)
        residuals = log_q - (intercept + slope * log_p)
        return {
            'beta': slope,
            'intercept': intercept,
            'r_squared': r_value ** 2,
            'p_value': p_value,
            'std_err': std_err,
            'residuals': residuals,
            'n': len(p),
        }
    except Exception as e:
        logger.warning("log-log regression failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Группа 1: Эластичность (H1a, H1b, H1c)
# ---------------------------------------------------------------------------


def test_elasticity_hypotheses(
    models_daily_data: dict,
    article_data: dict = None,
) -> dict:
    """
    Тестирует гипотезы H1a, H1b, H1c об эластичности спроса.

    H1a — эластичность различается между моделями (Kruskal-Wallis на резидуалах).
    H1b — эластичность различается между артикулами/цветами внутри модели.
    H1c — нелинейная (квадратичная) эластичность для отдельных моделей.

    Args:
        models_daily_data: {model_name: [dict(date, price_per_unit, sales_count)]}
        article_data: {article: [dict(date, price_per_unit, sales_count)]} (optional)

    Returns:
        dict с ключами H1a, H1b, H1c.
    """
    results = {}

    # --- H1a: эластичность различается между моделями ---
    try:
        model_elasticities = {}
        residual_groups = []
        for model_name, data_list in models_daily_data.items():
            df = pd.DataFrame(data_list)
            if len(df) < MIN_OBSERVATIONS:
                continue
            prices = df['price_per_unit'].values.astype(float)
            quantities = df['sales_count'].values.astype(float)
            reg = _safe_log_log_regression(prices, quantities)
            if reg is not None:
                model_elasticities[model_name] = reg['beta']
                residual_groups.append(reg['residuals'])

        if len(residual_groups) >= MIN_GROUPS:
            stat, p_val = stats.kruskal(*residual_groups)
            confirmed = p_val < 0.05
            results['H1a'] = _make_result(
                hypothesis="Эластичность спроса различается между моделями",
                result='confirmed' if confirmed else 'rejected',
                p_value=float(p_val),
                n_observations=sum(len(r) for r in residual_groups),
                details={
                    'kruskal_wallis_stat': round(float(stat), 3),
                    'n_models': len(residual_groups),
                    'elasticities': {
                        m: round(e, 3) for m, e in model_elasticities.items()
                    },
                },
            )
        else:
            results['H1a'] = _make_result(
                hypothesis="Эластичность спроса различается между моделями",
                result='inconclusive',
                p_value=None,
                n_observations=sum(len(r) for r in residual_groups),
                details={
                    'reason': f'Недостаточно моделей с данными (нужно {MIN_GROUPS}, есть {len(residual_groups)})',
                    'elasticities': {
                        m: round(e, 3) for m, e in model_elasticities.items()
                    },
                },
            )
    except Exception as e:
        logger.error("H1a test failed: %s", e, exc_info=True)
        results['H1a'] = _make_result(
            hypothesis="Эластичность спроса различается между моделями",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    # --- H1b: эластичность различается между артикулами/цветами ---
    try:
        if article_data is not None and len(article_data) >= MIN_GROUPS:
            article_betas = {}
            for article, data_list in article_data.items():
                df = pd.DataFrame(data_list)
                if len(df) < MIN_OBSERVATIONS:
                    continue
                prices = df['price_per_unit'].values.astype(float)
                quantities = df['sales_count'].values.astype(float)
                reg = _safe_log_log_regression(prices, quantities)
                if reg is not None:
                    article_betas[article] = reg['beta']

            if len(article_betas) >= MIN_GROUPS:
                betas = np.array(list(article_betas.values()))
                # F-test: between-article variance vs mean within-article SE
                between_var = np.var(betas, ddof=1)
                grand_mean = np.mean(betas)
                # Приближённый within-variance через SE каждого beta
                within_vars = []
                for article, data_list in article_data.items():
                    if article not in article_betas:
                        continue
                    df = pd.DataFrame(data_list)
                    prices = df['price_per_unit'].values.astype(float)
                    quantities = df['sales_count'].values.astype(float)
                    reg = _safe_log_log_regression(prices, quantities)
                    if reg is not None:
                        within_vars.append(reg['std_err'] ** 2)

                if within_vars:
                    mean_within_var = np.mean(within_vars)
                    if mean_within_var > 0:
                        f_stat = between_var / mean_within_var
                        df_between = len(article_betas) - 1
                        df_within = sum(
                            len(pd.DataFrame(article_data[a])) - 2
                            for a in article_betas
                        )
                        p_val = 1 - stats.f.cdf(f_stat, df_between, max(df_within, 1))
                        confirmed = p_val < 0.05
                        results['H1b'] = _make_result(
                            hypothesis="Эластичность различается между артикулами/цветами внутри модели",
                            result='confirmed' if confirmed else 'rejected',
                            p_value=float(p_val),
                            n_observations=sum(
                                len(pd.DataFrame(article_data[a]))
                                for a in article_betas
                            ),
                            details={
                                'f_stat': round(float(f_stat), 3),
                                'n_articles': len(article_betas),
                                'between_var': round(float(between_var), 4),
                                'within_var': round(float(mean_within_var), 4),
                                'article_elasticities': {
                                    a: round(b, 3) for a, b in article_betas.items()
                                },
                            },
                        )
                    else:
                        results['H1b'] = _make_result(
                            hypothesis="Эластичность различается между артикулами/цветами внутри модели",
                            result='inconclusive',
                            p_value=None,
                            n_observations=0,
                            details={'reason': 'Within-article variance = 0'},
                        )
                else:
                    results['H1b'] = _make_result(
                        hypothesis="Эластичность различается между артикулами/цветами внутри модели",
                        result='inconclusive',
                        p_value=None,
                        n_observations=0,
                        details={'reason': 'Не удалось вычислить within-article variance'},
                    )
            else:
                results['H1b'] = _make_result(
                    hypothesis="Эластичность различается между артикулами/цветами внутри модели",
                    result='inconclusive',
                    p_value=None,
                    n_observations=0,
                    details={
                        'reason': f'Недостаточно артикулов с данными (нужно {MIN_GROUPS}, есть {len(article_betas)})',
                    },
                )
        else:
            results['H1b'] = _make_result(
                hypothesis="Эластичность различается между артикулами/цветами внутри модели",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={'reason': 'article_data не предоставлен или менее 3 артикулов'},
            )
    except Exception as e:
        logger.error("H1b test failed: %s", e, exc_info=True)
        results['H1b'] = _make_result(
            hypothesis="Эластичность различается между артикулами/цветами внутри модели",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    # --- H1c: нелинейная (квадратичная) эластичность ---
    try:
        nonlinear_count = 0
        tested_count = 0
        nonlinear_models = []

        for model_name, data_list in models_daily_data.items():
            df = pd.DataFrame(data_list)
            mask = (df['price_per_unit'] > 0) & (df['sales_count'] > 0)
            df = df[mask]
            if len(df) < MIN_OBSERVATIONS:
                continue

            log_p = np.log(df['price_per_unit'].values.astype(float))
            log_q = np.log(df['sales_count'].values.astype(float))
            log_p_sq = log_p ** 2

            try:
                # Квадратичная регрессия через numpy polyfit (степень 2)
                # ln(Q) = a + b1*ln(P) + b2*ln(P)^2
                X = np.column_stack([np.ones(len(log_p)), log_p, log_p_sq])
                # OLS через np.linalg.lstsq
                coeffs, residuals_sum, rank, sv = np.linalg.lstsq(X, log_q, rcond=None)
                a, b1, b2 = coeffs

                # Вычисление p-value для b2
                n = len(log_q)
                k = 3  # количество параметров
                y_pred = X @ coeffs
                sse = np.sum((log_q - y_pred) ** 2)
                mse = sse / max(n - k, 1)
                # Стандартные ошибки коэффициентов
                try:
                    cov_matrix = mse * np.linalg.inv(X.T @ X)
                    se_b2 = np.sqrt(max(cov_matrix[2, 2], 0))
                    if se_b2 > 0:
                        t_stat = b2 / se_b2
                        p_val_b2 = 2 * (1 - stats.t.cdf(abs(t_stat), max(n - k, 1)))
                    else:
                        p_val_b2 = 1.0
                except np.linalg.LinAlgError:
                    p_val_b2 = 1.0

                tested_count += 1
                if p_val_b2 < 0.05:
                    nonlinear_count += 1
                    nonlinear_models.append({
                        'model': model_name,
                        'b2': round(float(b2), 4),
                        'b2_p_value': round(float(p_val_b2), 4),
                    })
            except Exception as e:
                logger.debug("H1c: модель %s пропущена (квадратичная регрессия): %s", model_name, e)
                continue

        if tested_count > 0:
            share = nonlinear_count / tested_count
            results['H1c'] = _make_result(
                hypothesis="Эластичность нелинейна (квадратичная зависимость ln(Q) от ln(P))",
                result='confirmed' if share >= 0.3 else 'rejected',
                p_value=None,
                n_observations=tested_count,
                details={
                    'nonlinear_count': nonlinear_count,
                    'tested_count': tested_count,
                    'nonlinear_share': round(share, 2),
                    'nonlinear_models': nonlinear_models,
                },
            )
        else:
            results['H1c'] = _make_result(
                hypothesis="Эластичность нелинейна (квадратичная зависимость ln(Q) от ln(P))",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={'reason': 'Ни одна модель не имеет достаточно данных'},
            )
    except Exception as e:
        logger.error("H1c test failed: %s", e, exc_info=True)
        results['H1c'] = _make_result(
            hypothesis="Эластичность нелинейна (квадратичная зависимость ln(Q) от ln(P))",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    return results


# ---------------------------------------------------------------------------
# Группа 2: Прибыль и маржинальность (H2a, H2b)
# ---------------------------------------------------------------------------


def test_profit_hypotheses(models_daily_data: dict) -> dict:
    """
    Тестирует гипотезы H2a и H2b о прибыли и маржинальности.

    H2a — существует оптимальная цена, максимизирующая margin_rub * sales_count.
    H2b — СПП% разрушает маржу быстрее, чем цена компенсирует.

    Args:
        models_daily_data: {model_name: [dict(date, price_per_unit, sales_count,
                            margin_rub, margin_pct, spp_pct)]}

    Returns:
        dict с ключами H2a, H2b.
    """
    results = {}

    # --- H2a: оптимальная цена для маржи * объёма ---
    try:
        model_results = []
        for model_name, data_list in models_daily_data.items():
            df = pd.DataFrame(data_list)
            if len(df) < MIN_OBSERVATIONS:
                continue
            mask = (df['price_per_unit'] > 0) & (df['sales_count'] > 0)
            df = df[mask]
            if len(df) < MIN_OBSERVATIONS:
                continue

            prices = df['price_per_unit'].values.astype(float)
            quantities = df['sales_count'].values.astype(float)
            reg = _safe_log_log_regression(prices, quantities)
            if reg is None:
                continue

            elasticity = reg['beta']
            # Grid search по ценовому диапазону
            price_min = np.percentile(prices, 5)
            price_max = np.percentile(prices, 95)
            if price_max <= price_min:
                continue

            # Оценка margin_rub на единицу (если есть)
            if 'margin_rub' in df.columns:
                margin_values = df['margin_rub'].values.astype(float)
                avg_margin_per_unit = np.mean(margin_values) / max(np.mean(quantities), 1e-6)
            else:
                # Приближение: маржа ~ доля от цены
                avg_price = np.mean(prices)
                if 'margin_pct' in df.columns:
                    avg_margin_pct = np.mean(df['margin_pct'].values.astype(float)) / 100.0
                else:
                    avg_margin_pct = 0.3  # fallback
                avg_margin_per_unit = avg_price * avg_margin_pct

            current_price = float(prices[-1])
            current_sales = float(quantities[-1])
            avg_cogs = current_price - avg_margin_per_unit

            test_prices = np.linspace(price_min, price_max, 50)
            best_profit = -np.inf
            best_price = current_price

            for p in test_prices:
                # Объём через эластичность: Q_new = Q_current * (P_new/P_current)^beta
                q = current_sales * (p / current_price) ** elasticity
                margin_per_unit = p - avg_cogs
                profit = margin_per_unit * q
                if profit > best_profit:
                    best_profit = profit
                    best_price = p

            gap_pct = (best_price - current_price) / current_price * 100 if current_price > 0 else 0

            model_results.append({
                'model': model_name,
                'current_price': round(current_price, 2),
                'optimal_price': round(float(best_price), 2),
                'gap_pct': round(float(gap_pct), 1),
                'elasticity': round(float(elasticity), 3),
            })

        if model_results:
            avg_gap = np.mean([abs(m['gap_pct']) for m in model_results])
            results['H2a'] = _make_result(
                hypothesis="Существует оптимальная цена, максимизирующая маржу × объём",
                result='confirmed' if avg_gap > 2.0 else 'rejected',
                p_value=None,
                n_observations=len(model_results),
                details={
                    'avg_gap_pct': round(float(avg_gap), 1),
                    'models': model_results,
                },
            )
        else:
            results['H2a'] = _make_result(
                hypothesis="Существует оптимальная цена, максимизирующая маржу × объём",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={'reason': 'Недостаточно моделей с данными'},
            )
    except Exception as e:
        logger.error("H2a test failed: %s", e, exc_info=True)
        results['H2a'] = _make_result(
            hypothesis="Существует оптимальная цена, максимизирующая маржу × объём",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    # --- H2b: SPP% разрушает маржу быстрее, чем цена компенсирует ---
    try:
        spp_dominates_count = 0
        tested_count = 0

        for model_name, data_list in models_daily_data.items():
            df = pd.DataFrame(data_list)
            required_cols = {'price_per_unit', 'margin_pct', 'spp_pct'}
            if not required_cols.issubset(df.columns):
                continue
            df = df.dropna(subset=list(required_cols))
            if len(df) < MIN_OBSERVATIONS:
                continue

            # Стандартизация для сравнения коэффициентов
            y = df['margin_pct'].values.astype(float)
            x_price = df['price_per_unit'].values.astype(float)
            x_spp = df['spp_pct'].values.astype(float)

            # z-score стандартизация
            y_std = (y - np.mean(y)) / (np.std(y) + 1e-10)
            x_price_std = (x_price - np.mean(x_price)) / (np.std(x_price) + 1e-10)
            x_spp_std = (x_spp - np.mean(x_spp)) / (np.std(x_spp) + 1e-10)

            X = np.column_stack([np.ones(len(y_std)), x_price_std, x_spp_std])
            try:
                coeffs, _, _, _ = np.linalg.lstsq(X, y_std, rcond=None)
                beta_price = abs(coeffs[1])
                beta_spp = abs(coeffs[2])
                tested_count += 1
                if beta_spp > beta_price:
                    spp_dominates_count += 1
            except Exception as e:
                logger.debug("H2b: модель %s пропущена (lstsq): %s", model_name, e)
                continue

        if tested_count > 0:
            share = spp_dominates_count / tested_count
            results['H2b'] = _make_result(
                hypothesis="СПП% разрушает маржу быстрее, чем цена компенсирует",
                result='confirmed' if share > 0.5 else 'rejected',
                p_value=None,
                n_observations=tested_count,
                details={
                    'spp_dominates_count': spp_dominates_count,
                    'tested_count': tested_count,
                    'spp_dominates_share': round(share, 2),
                },
            )
        else:
            results['H2b'] = _make_result(
                hypothesis="СПП% разрушает маржу быстрее, чем цена компенсирует",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={'reason': 'Нет моделей с price_per_unit, margin_pct, spp_pct'},
            )
    except Exception as e:
        logger.error("H2b test failed: %s", e, exc_info=True)
        results['H2b'] = _make_result(
            hypothesis="СПП% разрушает маржу быстрее, чем цена компенсирует",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    return results


# ---------------------------------------------------------------------------
# Группа 3: Реклама (H3a, H3b)
# ---------------------------------------------------------------------------


def test_advertising_hypotheses(models_daily_data: dict) -> dict:
    """
    Тестирует гипотезы H3a и H3b о рекламной эффективности.

    H3a — ДРР% имеет убывающую отдачу (diminishing returns).
    H3b — рекламная эластичность различается между моделями.

    Args:
        models_daily_data: {model_name: [dict(date, sales_count, adv_total, price_per_unit)]}

    Returns:
        dict с ключами H3a, H3b.
    """
    results = {}

    # --- H3a: убывающая отдача рекламы ---
    try:
        diminishing_count = 0
        tested_count = 0
        model_details = []

        for model_name, data_list in models_daily_data.items():
            df = pd.DataFrame(data_list)
            if 'adv_total' not in df.columns:
                continue
            mask = (df['adv_total'] > 0) & (df['sales_count'] > 0)
            df = df[mask]
            if len(df) < MIN_OBSERVATIONS:
                continue

            adv = df['adv_total'].values.astype(float)
            sales = df['sales_count'].values.astype(float)
            median_adv = np.median(adv)

            low_mask = adv <= median_adv
            high_mask = adv > median_adv
            if low_mask.sum() < 5 or high_mask.sum() < 5:
                continue

            # Линейная регрессия по каждой половине
            slope_low, _, _, _, _ = stats.linregress(adv[low_mask], sales[low_mask])
            slope_high, _, _, _, _ = stats.linregress(adv[high_mask], sales[high_mask])

            tested_count += 1
            is_diminishing = slope_high < slope_low
            if is_diminishing:
                diminishing_count += 1

            model_details.append({
                'model': model_name,
                'slope_low': round(float(slope_low), 4),
                'slope_high': round(float(slope_high), 4),
                'is_diminishing': is_diminishing,
                'n_low': int(low_mask.sum()),
                'n_high': int(high_mask.sum()),
            })

        if tested_count > 0:
            share = diminishing_count / tested_count
            results['H3a'] = _make_result(
                hypothesis="ДРР% имеет убывающую отдачу (diminishing returns)",
                result='confirmed' if share > 0.5 else 'rejected',
                p_value=None,
                n_observations=tested_count,
                details={
                    'diminishing_count': diminishing_count,
                    'tested_count': tested_count,
                    'share': round(share, 2),
                    'models': model_details,
                },
            )
        else:
            results['H3a'] = _make_result(
                hypothesis="ДРР% имеет убывающую отдачу (diminishing returns)",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={'reason': 'Нет моделей с достаточными данными по рекламе'},
            )
    except Exception as e:
        logger.error("H3a test failed: %s", e, exc_info=True)
        results['H3a'] = _make_result(
            hypothesis="ДРР% имеет убывающую отдачу (diminishing returns)",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    # --- H3b: рекламная эластичность различается между моделями ---
    try:
        ad_elasticities = {}

        for model_name, data_list in models_daily_data.items():
            df = pd.DataFrame(data_list)
            if 'adv_total' not in df.columns:
                continue
            mask = (
                (df['adv_total'] > 0)
                & (df['sales_count'] > 0)
                & (df['price_per_unit'] > 0)
            )
            df = df[mask]
            if len(df) < MIN_OBSERVATIONS:
                continue

            log_sales = np.log(df['sales_count'].values.astype(float))
            log_adv = np.log(df['adv_total'].values.astype(float))
            log_price = np.log(df['price_per_unit'].values.astype(float))

            # Множественная регрессия: ln(sales) = a + b*ln(adv) + c*ln(price)
            X = np.column_stack([np.ones(len(log_sales)), log_adv, log_price])
            try:
                coeffs, _, _, _ = np.linalg.lstsq(X, log_sales, rcond=None)
                ad_elasticities[model_name] = coeffs[1]  # beta для ln(adv)
            except np.linalg.LinAlgError:
                continue

        if len(ad_elasticities) >= MIN_GROUPS:
            # Kruskal-Wallis: нужны «группы» значений
            # Для каждой модели у нас одно значение эластичности,
            # используем bootstrap-подход: сравниваем распределения резидуалов
            # Упрощённый вариант: тест на равенство средних через chi2
            values = np.array(list(ad_elasticities.values()))
            overall_mean = np.mean(values)
            overall_std = np.std(values, ddof=1)

            if overall_std > 1e-10:
                # Тест: разброс эластичностей значим?
                # Используем chi-squared тест на однородность
                chi2_stat = np.sum((values - overall_mean) ** 2) / (overall_std ** 2)
                df_chi = len(values) - 1
                p_val = 1 - stats.chi2.cdf(chi2_stat, df_chi)

                confirmed = p_val < 0.05
                results['H3b'] = _make_result(
                    hypothesis="Рекламная эластичность различается между моделями",
                    result='confirmed' if confirmed else 'rejected',
                    p_value=float(p_val),
                    n_observations=len(ad_elasticities),
                    details={
                        'chi2_stat': round(float(chi2_stat), 3),
                        'n_models': len(ad_elasticities),
                        'ad_elasticities': {
                            m: round(float(e), 3) for m, e in ad_elasticities.items()
                        },
                        'mean_ad_elasticity': round(float(overall_mean), 3),
                        'std_ad_elasticity': round(float(overall_std), 3),
                    },
                )
            else:
                results['H3b'] = _make_result(
                    hypothesis="Рекламная эластичность различается между моделями",
                    result='rejected',
                    p_value=1.0,
                    n_observations=len(ad_elasticities),
                    details={
                        'reason': 'Нулевой разброс эластичностей',
                        'ad_elasticities': {
                            m: round(float(e), 3) for m, e in ad_elasticities.items()
                        },
                    },
                )
        else:
            results['H3b'] = _make_result(
                hypothesis="Рекламная эластичность различается между моделями",
                result='inconclusive',
                p_value=None,
                n_observations=len(ad_elasticities),
                details={
                    'reason': f'Недостаточно моделей (нужно {MIN_GROUPS}, есть {len(ad_elasticities)})',
                },
            )
    except Exception as e:
        logger.error("H3b test failed: %s", e, exc_info=True)
        results['H3b'] = _make_result(
            hypothesis="Рекламная эластичность различается между моделями",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    return results


# ---------------------------------------------------------------------------
# Группа 4: Запасы (H4a, H4b)
# ---------------------------------------------------------------------------


def test_stock_hypotheses(
    models_daily_data: dict,
    stock_daily_data: dict,
) -> dict:
    """
    Тестирует гипотезы H4a и H4b о влиянии запасов.

    H4a — низкий сток (< 2 недели) снижает продажи (Welch t-test).
    H4b — высокий сток (> 8 недель) — сигнал к снижению цены.

    Args:
        models_daily_data: {model: [dict(date, sales_count, margin_pct)]}
        stock_daily_data: {model: [dict(date, total_stock)]}

    Returns:
        dict с ключами H4a, H4b.
    """
    results = {}

    if stock_daily_data is None:
        for key in ('H4a', 'H4b'):
            results[key] = _make_result(
                hypothesis=f"Stock hypothesis {key}",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={'reason': 'stock_daily_data не предоставлен'},
            )
        return results

    # --- H4a: низкий сток снижает продажи ---
    try:
        low_stock_sales = []
        healthy_stock_sales = []
        n_total = 0

        for model_name, sales_data in models_daily_data.items():
            if model_name not in stock_daily_data:
                continue

            df_sales = pd.DataFrame(sales_data)
            df_stock = pd.DataFrame(stock_daily_data[model_name])

            if 'date' not in df_sales.columns or 'date' not in df_stock.columns:
                continue

            df_sales['date'] = pd.to_datetime(df_sales['date'])
            df_stock['date'] = pd.to_datetime(df_stock['date'])

            merged = pd.merge(df_sales, df_stock, on='date', how='inner')
            if len(merged) < MIN_OBSERVATIONS:
                continue

            # 7-дневное скользящее среднее продаж
            merged = merged.sort_values('date')
            merged['rolling_sales_7d'] = (
                merged['sales_count']
                .rolling(window=7, min_periods=1)
                .mean()
            )

            # weeks_supply = total_stock / (rolling_sales_7d * 7)
            merged['weeks_supply'] = merged['total_stock'] / (
                merged['rolling_sales_7d'] * 7 + 1e-6
            )

            low = merged[merged['weeks_supply'] < 2]['sales_count'].values
            healthy = merged[
                (merged['weeks_supply'] >= 2) & (merged['weeks_supply'] <= 8)
            ]['sales_count'].values

            low_stock_sales.extend(low.tolist())
            healthy_stock_sales.extend(healthy.tolist())
            n_total += len(merged)

        if len(low_stock_sales) >= 10 and len(healthy_stock_sales) >= 10:
            t_stat, p_val = stats.ttest_ind(
                healthy_stock_sales, low_stock_sales, equal_var=False
            )
            # Если healthy > low (t > 0), подтверждает что низкий сток снижает продажи
            confirmed = p_val < 0.05 and t_stat > 0
            results['H4a'] = _make_result(
                hypothesis="Низкий сток (< 2 недель) снижает продажи",
                result='confirmed' if confirmed else 'rejected',
                p_value=float(p_val),
                n_observations=n_total,
                details={
                    'welch_t_stat': round(float(t_stat), 3),
                    'n_low_stock_days': len(low_stock_sales),
                    'n_healthy_stock_days': len(healthy_stock_sales),
                    'avg_sales_low_stock': round(float(np.mean(low_stock_sales)), 2),
                    'avg_sales_healthy': round(float(np.mean(healthy_stock_sales)), 2),
                    'sales_drop_pct': round(
                        (1 - np.mean(low_stock_sales) / max(np.mean(healthy_stock_sales), 1e-6))
                        * 100,
                        1,
                    ),
                },
            )
        else:
            results['H4a'] = _make_result(
                hypothesis="Низкий сток (< 2 недель) снижает продажи",
                result='inconclusive',
                p_value=None,
                n_observations=n_total,
                details={
                    'reason': 'Недостаточно наблюдений в группах',
                    'n_low': len(low_stock_sales),
                    'n_healthy': len(healthy_stock_sales),
                },
            )
    except Exception as e:
        logger.error("H4a test failed: %s", e, exc_info=True)
        results['H4a'] = _make_result(
            hypothesis="Низкий сток (< 2 недель) снижает продажи",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    # --- H4b: высокий сток (> 8 недель) — сигнал к снижению цены ---
    try:
        overstocked_margins = []
        healthy_margins = []
        n_total = 0

        for model_name, sales_data in models_daily_data.items():
            if model_name not in stock_daily_data:
                continue

            df_sales = pd.DataFrame(sales_data)
            df_stock = pd.DataFrame(stock_daily_data[model_name])

            if 'margin_pct' not in df_sales.columns:
                continue
            if 'date' not in df_sales.columns or 'date' not in df_stock.columns:
                continue

            df_sales['date'] = pd.to_datetime(df_sales['date'])
            df_stock['date'] = pd.to_datetime(df_stock['date'])

            merged = pd.merge(df_sales, df_stock, on='date', how='inner')
            if len(merged) < MIN_OBSERVATIONS:
                continue

            merged = merged.sort_values('date')
            merged['rolling_sales_7d'] = (
                merged['sales_count']
                .rolling(window=7, min_periods=1)
                .mean()
            )
            merged['weeks_supply'] = merged['total_stock'] / (
                merged['rolling_sales_7d'] * 7 + 1e-6
            )

            overstocked = merged[merged['weeks_supply'] > 8]['margin_pct'].values
            healthy = merged[
                (merged['weeks_supply'] >= 2) & (merged['weeks_supply'] <= 8)
            ]['margin_pct'].values

            overstocked_margins.extend(overstocked.tolist())
            healthy_margins.extend(healthy.tolist())
            n_total += len(merged)

        if len(overstocked_margins) >= 10 and len(healthy_margins) >= 10:
            t_stat, p_val = stats.ttest_ind(
                overstocked_margins, healthy_margins, equal_var=False
            )
            results['H4b'] = _make_result(
                hypothesis="Высокий сток (> 8 недель) — сигнал к снижению цены",
                result='confirmed' if p_val < 0.05 else 'rejected',
                p_value=float(p_val),
                n_observations=n_total,
                details={
                    'welch_t_stat': round(float(t_stat), 3),
                    'n_overstocked_days': len(overstocked_margins),
                    'n_healthy_days': len(healthy_margins),
                    'avg_margin_overstocked': round(float(np.mean(overstocked_margins)), 2),
                    'avg_margin_healthy': round(float(np.mean(healthy_margins)), 2),
                },
            )
        else:
            results['H4b'] = _make_result(
                hypothesis="Высокий сток (> 8 недель) — сигнал к снижению цены",
                result='inconclusive',
                p_value=None,
                n_observations=n_total,
                details={
                    'reason': 'Недостаточно наблюдений в группах',
                    'n_overstocked': len(overstocked_margins),
                    'n_healthy': len(healthy_margins),
                },
            )
    except Exception as e:
        logger.error("H4b test failed: %s", e, exc_info=True)
        results['H4b'] = _make_result(
            hypothesis="Высокий сток (> 8 недель) — сигнал к снижению цены",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    return results


# ---------------------------------------------------------------------------
# Группа 5: Кросс-модельные эффекты (H5a)
# ---------------------------------------------------------------------------


def test_cross_model_hypotheses(
    models_daily_data: dict,
    product_lines: dict = None,
) -> dict:
    """
    Тестирует гипотезу H5a о каннибализации между моделями.

    H5a — повышение цены модели A увеличивает продажи модели B (в той же линейке).

    Args:
        models_daily_data: {model: [dict(date, price_per_unit, sales_count)]}
        product_lines: {line_name: [model_names]} — группировка моделей по линейкам.

    Returns:
        dict с ключом H5a.
    """
    results = {}

    if product_lines is None:
        product_lines = {
            'seamless': ['wendy', 'audrey'],
            'tricot': ['ruby', 'set_vuki'],
        }

    try:
        pair_results = []
        total_pairs_tested = 0

        for line_name, model_names in product_lines.items():
            # Все модели линейки, имеющиеся в данных
            available_models = [m for m in model_names if m in models_daily_data]
            if len(available_models) < 2:
                continue

            for i, model_a in enumerate(available_models):
                for model_b in available_models[i + 1:]:
                    df_a = pd.DataFrame(models_daily_data[model_a])
                    df_b = pd.DataFrame(models_daily_data[model_b])

                    if 'date' not in df_a.columns or 'date' not in df_b.columns:
                        continue

                    df_a['date'] = pd.to_datetime(df_a['date'])
                    df_b['date'] = pd.to_datetime(df_b['date'])

                    merged = pd.merge(
                        df_a[['date', 'price_per_unit', 'sales_count']],
                        df_b[['date', 'price_per_unit', 'sales_count']],
                        on='date',
                        suffixes=('_a', '_b'),
                    )

                    if len(merged) < MIN_OBSERVATIONS:
                        continue

                    # Фильтр: положительные значения
                    mask = (
                        (merged['price_per_unit_a'] > 0)
                        & (merged['price_per_unit_b'] > 0)
                        & (merged['sales_count_b'] > 0)
                    )
                    merged = merged[mask]
                    if len(merged) < MIN_OBSERVATIONS:
                        continue

                    # Регрессия: ln(sales_B) = a + b1*ln(price_A) + b2*ln(price_B)
                    log_sales_b = np.log(merged['sales_count_b'].values.astype(float))
                    log_price_a = np.log(merged['price_per_unit_a'].values.astype(float))
                    log_price_b = np.log(merged['price_per_unit_b'].values.astype(float))

                    X = np.column_stack([
                        np.ones(len(log_sales_b)),
                        log_price_a,
                        log_price_b,
                    ])
                    try:
                        coeffs, _, _, _ = np.linalg.lstsq(X, log_sales_b, rcond=None)
                        beta_price_a = coeffs[1]

                        # P-value через t-test
                        n = len(log_sales_b)
                        k = 3
                        y_pred = X @ coeffs
                        sse = np.sum((log_sales_b - y_pred) ** 2)
                        mse = sse / max(n - k, 1)
                        try:
                            cov_mat = mse * np.linalg.inv(X.T @ X)
                            se_b1 = np.sqrt(max(cov_mat[1, 1], 0))
                            if se_b1 > 0:
                                t_stat = beta_price_a / se_b1
                                p_val = 2 * (1 - stats.t.cdf(abs(t_stat), max(n - k, 1)))
                            else:
                                p_val = 1.0
                        except np.linalg.LinAlgError:
                            p_val = 1.0

                        # Положительный beta_price_a означает каннибализацию
                        is_cannibalization = beta_price_a > 0 and p_val < 0.05

                        total_pairs_tested += 1
                        pair_results.append({
                            'line': line_name,
                            'model_a': model_a,
                            'model_b': model_b,
                            'beta_price_a_on_sales_b': round(float(beta_price_a), 3),
                            'p_value': round(float(p_val), 4),
                            'is_cannibalization': is_cannibalization,
                            'n_overlapping_days': len(merged),
                        })
                    except np.linalg.LinAlgError:
                        continue

        if total_pairs_tested > 0:
            cannibalization_count = sum(1 for p in pair_results if p['is_cannibalization'])
            results['H5a'] = _make_result(
                hypothesis="Повышение цены модели A увеличивает продажи модели B (каннибализация)",
                result='confirmed' if cannibalization_count > 0 else 'rejected',
                p_value=None,
                n_observations=total_pairs_tested,
                details={
                    'cannibalization_pairs': cannibalization_count,
                    'total_pairs': total_pairs_tested,
                    'pairs': pair_results,
                },
            )
        else:
            results['H5a'] = _make_result(
                hypothesis="Повышение цены модели A увеличивает продажи модели B (каннибализация)",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={
                    'reason': 'Нет пар моделей с достаточным пересечением дат',
                    'product_lines': product_lines,
                },
            )
    except Exception as e:
        logger.error("H5a test failed: %s", e, exc_info=True)
        results['H5a'] = _make_result(
            hypothesis="Повышение цены модели A увеличивает продажи модели B (каннибализация)",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    return results


# ---------------------------------------------------------------------------
# Группа 6: Временные паттерны (H6a, H6b)
# ---------------------------------------------------------------------------


def test_temporal_hypotheses(models_daily_data: dict) -> dict:
    """
    Тестирует гипотезы H6a и H6b о временных паттернах.

    H6a — эластичность меняется по сезонам (кварталам).
    H6b — эффект дня недели на продажи.

    Args:
        models_daily_data: {model: [dict(date, price_per_unit, sales_count)]}

    Returns:
        dict с ключами H6a, H6b.
    """
    results = {}

    # --- H6a: сезонность эластичности ---
    try:
        seasonal_results = []
        tested_count = 0

        for model_name, data_list in models_daily_data.items():
            df = pd.DataFrame(data_list)
            if 'date' not in df.columns:
                continue
            df['date'] = pd.to_datetime(df['date'])
            if len(df) < MIN_DAYS_SEASONAL:
                continue

            df['quarter'] = df['date'].dt.quarter
            quarterly_betas = []

            for q in sorted(df['quarter'].unique()):
                q_data = df[df['quarter'] == q]
                if len(q_data) < MIN_OBSERVATIONS:
                    continue
                prices = q_data['price_per_unit'].values.astype(float)
                quantities = q_data['sales_count'].values.astype(float)
                reg = _safe_log_log_regression(prices, quantities)
                if reg is not None:
                    quarterly_betas.append(reg['beta'])

            if len(quarterly_betas) >= 2:
                tested_count += 1
                beta_variance = np.var(quarterly_betas, ddof=1)
                seasonal_results.append({
                    'model': model_name,
                    'quarterly_betas': [round(b, 3) for b in quarterly_betas],
                    'beta_variance': round(float(beta_variance), 4),
                    'n_quarters': len(quarterly_betas),
                })

        if tested_count > 0:
            # Агрегируем: если у большинства моделей высокая вариация — confirmed
            all_variances = [s['beta_variance'] for s in seasonal_results]
            # F-test: pooled variance vs expected under H0 (no seasonal effect)
            mean_variance = np.mean(all_variances)

            # Простой критерий: если коэффициент вариации бета > 30%, то эффект есть
            all_betas_flat = []
            for s in seasonal_results:
                all_betas_flat.extend(s['quarterly_betas'])
            if all_betas_flat:
                overall_mean = np.mean(all_betas_flat)
                overall_cv = np.std(all_betas_flat, ddof=1) / (abs(overall_mean) + 1e-6)
            else:
                overall_cv = 0

            confirmed = overall_cv > 0.3

            results['H6a'] = _make_result(
                hypothesis="Эластичность меняется по сезонам (кварталам)",
                result='confirmed' if confirmed else 'rejected',
                p_value=None,
                n_observations=tested_count,
                details={
                    'overall_elasticity_cv': round(float(overall_cv), 3),
                    'mean_quarterly_variance': round(float(mean_variance), 4),
                    'models': seasonal_results,
                },
            )
        else:
            results['H6a'] = _make_result(
                hypothesis="Эластичность меняется по сезонам (кварталам)",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={
                    'reason': f'Нет моделей с данными >= {MIN_DAYS_SEASONAL} дней '
                              f'и >= 2 кварталов',
                },
            )
    except Exception as e:
        logger.error("H6a test failed: %s", e, exc_info=True)
        results['H6a'] = _make_result(
            hypothesis="Эластичность меняется по сезонам (кварталам)",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    # --- H6b: эффект дня недели ---
    try:
        dow_significant_count = 0
        tested_count = 0
        model_details = []

        for model_name, data_list in models_daily_data.items():
            df = pd.DataFrame(data_list)
            if 'date' not in df.columns:
                continue
            df['date'] = pd.to_datetime(df['date'])
            if len(df) < MIN_OBSERVATIONS * 2:
                continue

            mask = (df['price_per_unit'] > 0) & (df['sales_count'] > 0)
            df = df[mask]
            if len(df) < MIN_OBSERVATIONS * 2:
                continue

            # Dummy-переменные для дня недели (0=Пн, 6=Вс)
            df['dow'] = df['date'].dt.dayofweek
            dummies = pd.get_dummies(df['dow'], prefix='dow', drop_first=True)
            dummies = dummies.astype(float)

            log_sales = np.log(df['sales_count'].values.astype(float))
            log_price = np.log(df['price_per_unit'].values.astype(float))

            # Restricted model: log_sales ~ log_price
            X_restricted = np.column_stack([np.ones(len(log_sales)), log_price])
            try:
                coeffs_r, _, _, _ = np.linalg.lstsq(X_restricted, log_sales, rcond=None)
                if not np.all(np.isfinite(coeffs_r)):
                    continue
                with np.errstate(over='ignore', invalid='ignore'):
                    sse_restricted = np.sum((log_sales - X_restricted @ coeffs_r) ** 2)
                if not np.isfinite(sse_restricted):
                    continue
            except np.linalg.LinAlgError:
                continue

            # Full model: log_sales ~ log_price + dow_dummies
            X_full = np.column_stack([
                np.ones(len(log_sales)),
                log_price,
                dummies.values,
            ])
            try:
                coeffs_f, _, _, _ = np.linalg.lstsq(X_full, log_sales, rcond=None)
                if not np.all(np.isfinite(coeffs_f)):
                    continue
                with np.errstate(over='ignore', invalid='ignore'):
                    sse_full = np.sum((log_sales - X_full @ coeffs_f) ** 2)
                if not np.isfinite(sse_full):
                    continue
            except np.linalg.LinAlgError:
                continue

            # F-test для совместной значимости дамми-переменных
            n = len(log_sales)
            p_restricted = X_restricted.shape[1]
            p_full = X_full.shape[1]
            df_num = p_full - p_restricted
            df_den = n - p_full

            if df_den > 0 and sse_full > 0:
                f_stat = ((sse_restricted - sse_full) / df_num) / (sse_full / df_den)
                p_val = 1 - stats.f.cdf(f_stat, df_num, df_den)

                tested_count += 1
                if p_val < 0.05:
                    dow_significant_count += 1

                model_details.append({
                    'model': model_name,
                    'f_stat': round(float(f_stat), 3),
                    'p_value': round(float(p_val), 4),
                    'is_significant': p_val < 0.05,
                    'n': n,
                })

        if tested_count > 0:
            share = dow_significant_count / tested_count
            results['H6b'] = _make_result(
                hypothesis="День недели влияет на продажи",
                result='confirmed' if share > 0.5 else 'rejected',
                p_value=None,
                n_observations=tested_count,
                details={
                    'significant_count': dow_significant_count,
                    'tested_count': tested_count,
                    'share': round(share, 2),
                    'models': model_details,
                },
            )
        else:
            results['H6b'] = _make_result(
                hypothesis="День недели влияет на продажи",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={'reason': 'Нет моделей с достаточными данными'},
            )
    except Exception as e:
        logger.error("H6b test failed: %s", e, exc_info=True)
        results['H6b'] = _make_result(
            hypothesis="День недели влияет на продажи",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    return results


# ---------------------------------------------------------------------------
# Группа 7: ROI (H7a, H7b)
# ---------------------------------------------------------------------------


def test_roi_hypotheses(
    models_daily_data: dict,
    turnover_data: dict,
) -> dict:
    """
    Тестирует гипотезы H7a и H7b о ROI.

    H7a — ранжирование моделей по annual_roi = margin_pct * 365 / turnover_days.
    H7b — оптимальная цена для ROI != оптимальная для margin%.

    Args:
        models_daily_data: {model: [dict(date, price_per_unit, sales_count, margin_pct)]}
        turnover_data: {model: {turnover_days, avg_stock, daily_sales}}

    Returns:
        dict с ключами H7a, H7b.
    """
    from agents.oleg.services.price_analysis.roi_optimizer import compute_annual_roi

    results = {}

    if turnover_data is None:
        for key in ('H7a', 'H7b'):
            results[key] = _make_result(
                hypothesis=f"ROI hypothesis {key}",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={'reason': 'turnover_data не предоставлен'},
            )
        return results

    # --- H7a: ранжирование моделей по ROI ---
    try:
        roi_ranking = []
        for model_name, data_list in models_daily_data.items():
            if model_name not in turnover_data:
                continue

            df = pd.DataFrame(data_list)
            if 'margin_pct' not in df.columns or len(df) < 7:
                continue

            avg_margin_pct = float(df['margin_pct'].mean())
            td = turnover_data[model_name]
            turnover_days = float(td.get('turnover_days', 9999))

            annual_roi = compute_annual_roi(avg_margin_pct, turnover_days)

            roi_ranking.append({
                'model': model_name,
                'margin_pct': round(avg_margin_pct, 2),
                'turnover_days': round(turnover_days, 1),
                'annual_roi': round(annual_roi, 2),
            })

        roi_ranking.sort(key=lambda x: x['annual_roi'], reverse=True)

        # Информационный результат — всегда confirmed если есть данные
        if roi_ranking:
            results['H7a'] = _make_result(
                hypothesis="Ранжирование моделей по annual_roi = margin_pct * 365 / turnover_days",
                result='confirmed',
                p_value=None,
                n_observations=len(roi_ranking),
                details={
                    'ranking': roi_ranking,
                    'best_model': roi_ranking[0]['model'] if roi_ranking else None,
                    'worst_model': roi_ranking[-1]['model'] if roi_ranking else None,
                },
            )
        else:
            results['H7a'] = _make_result(
                hypothesis="Ранжирование моделей по annual_roi = margin_pct * 365 / turnover_days",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={'reason': 'Нет данных оборачиваемости'},
            )
    except Exception as e:
        logger.error("H7a test failed: %s", e, exc_info=True)
        results['H7a'] = _make_result(
            hypothesis="Ранжирование моделей по annual_roi = margin_pct * 365 / turnover_days",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    # --- H7b: оптимальная цена для ROI != оптимальная для margin% ---
    try:
        models_divergent = []
        tested_count = 0

        for model_name, data_list in models_daily_data.items():
            if model_name not in turnover_data:
                continue

            df = pd.DataFrame(data_list)
            mask = (df['price_per_unit'] > 0) & (df['sales_count'] > 0)
            df = df[mask]
            if len(df) < MIN_OBSERVATIONS or 'margin_pct' not in df.columns:
                continue

            prices = df['price_per_unit'].values.astype(float)
            quantities = df['sales_count'].values.astype(float)
            reg = _safe_log_log_regression(prices, quantities)
            if reg is None:
                continue

            elasticity = reg['beta']
            td = turnover_data[model_name]
            turnover_days = float(td.get('turnover_days', 9999))
            avg_stock = float(td.get('avg_stock', 0))

            current_price = float(np.mean(prices))
            current_sales = float(np.mean(quantities))
            avg_margin_pct = float(df['margin_pct'].mean()) / 100.0
            avg_margin_per_unit = current_price * avg_margin_pct
            avg_cogs = current_price - avg_margin_per_unit

            # Grid search для margin% optimal
            price_min = np.percentile(prices, 5)
            price_max = np.percentile(prices, 95)
            if price_max <= price_min:
                continue

            test_prices = np.linspace(price_min, price_max, 50)

            best_margin_pct = -np.inf
            best_price_margin = current_price

            best_roi = -np.inf
            best_price_roi = current_price

            for p in test_prices:
                q = current_sales * (p / current_price) ** elasticity
                margin_per_unit = p - avg_cogs
                margin_pct = (margin_per_unit / p * 100) if p > 0 else 0

                # Optimal for margin%
                if margin_pct > best_margin_pct:
                    best_margin_pct = margin_pct
                    best_price_margin = p

                # Optimal for ROI
                if q > 0 and avg_stock > 0:
                    new_turnover = avg_stock / q
                    roi = compute_annual_roi(margin_pct, new_turnover)
                else:
                    roi = 0

                if roi > best_roi:
                    best_roi = roi
                    best_price_roi = p

            # Сравнение оптимальных цен
            if best_price_margin > 0:
                price_diff_pct = abs(best_price_roi - best_price_margin) / best_price_margin * 100
            else:
                price_diff_pct = 0

            tested_count += 1
            if price_diff_pct > 2:
                models_divergent.append({
                    'model': model_name,
                    'optimal_price_margin': round(float(best_price_margin), 2),
                    'optimal_price_roi': round(float(best_price_roi), 2),
                    'price_diff_pct': round(float(price_diff_pct), 1),
                })

        if tested_count > 0:
            confirmed = len(models_divergent) > 0
            results['H7b'] = _make_result(
                hypothesis="Оптимальная цена для ROI отличается от оптимальной для margin%",
                result='confirmed' if confirmed else 'rejected',
                p_value=None,
                n_observations=tested_count,
                details={
                    'divergent_models': len(models_divergent),
                    'tested_count': tested_count,
                    'models': models_divergent,
                },
            )
        else:
            results['H7b'] = _make_result(
                hypothesis="Оптимальная цена для ROI отличается от оптимальной для margin%",
                result='inconclusive',
                p_value=None,
                n_observations=0,
                details={'reason': 'Нет моделей с эластичностью и данными оборачиваемости'},
            )
    except Exception as e:
        logger.error("H7b test failed: %s", e, exc_info=True)
        results['H7b'] = _make_result(
            hypothesis="Оптимальная цена для ROI отличается от оптимальной для margin%",
            result='inconclusive',
            p_value=None,
            n_observations=0,
            details={'error': str(e)},
        )

    return results


# ---------------------------------------------------------------------------
# Оркестратор: запуск всех гипотез
# ---------------------------------------------------------------------------


def run_all_hypotheses(
    models_daily_data: dict,
    article_data: dict = None,
    stock_daily_data: dict = None,
    turnover_data: dict = None,
    product_lines: dict = None,
) -> dict:
    """
    Запускает все 14 гипотез по 7 группам и агрегирует результаты.

    Args:
        models_daily_data: {model: [dict]} — ежедневные данные по моделям.
        article_data: {article: [dict]} — данные по артикулам (для H1b).
        stock_daily_data: {model: [dict(date, total_stock)]} — ежедневные остатки (для H4).
        turnover_data: {model: {turnover_days, avg_stock, daily_sales}} — оборачиваемость (для H7).
        product_lines: {line: [models]} — группировка моделей (для H5a).

    Returns:
        dict с tested_at, total_hypotheses, confirmed, rejected, inconclusive,
        results, summary.
    """
    all_results = {}

    # Группа 1: Эластичность
    try:
        h1 = test_elasticity_hypotheses(models_daily_data, article_data)
        all_results.update(h1)
    except Exception as e:
        logger.error("Elasticity hypotheses group failed: %s", e, exc_info=True)

    # Группа 2: Прибыль
    try:
        h2 = test_profit_hypotheses(models_daily_data)
        all_results.update(h2)
    except Exception as e:
        logger.error("Profit hypotheses group failed: %s", e, exc_info=True)

    # Группа 3: Реклама
    try:
        h3 = test_advertising_hypotheses(models_daily_data)
        all_results.update(h3)
    except Exception as e:
        logger.error("Advertising hypotheses group failed: %s", e, exc_info=True)

    # Группа 4: Запасы
    try:
        if stock_daily_data is not None:
            h4 = test_stock_hypotheses(models_daily_data, stock_daily_data)
            all_results.update(h4)
        else:
            for key in ('H4a', 'H4b'):
                all_results[key] = _make_result(
                    hypothesis=f"Stock hypothesis {key}",
                    result='inconclusive',
                    p_value=None,
                    n_observations=0,
                    details={'reason': 'stock_daily_data не предоставлен'},
                )
    except Exception as e:
        logger.error("Stock hypotheses group failed: %s", e, exc_info=True)

    # Группа 5: Кросс-модельные
    try:
        h5 = test_cross_model_hypotheses(models_daily_data, product_lines)
        all_results.update(h5)
    except Exception as e:
        logger.error("Cross-model hypotheses group failed: %s", e, exc_info=True)

    # Группа 6: Временные паттерны
    try:
        h6 = test_temporal_hypotheses(models_daily_data)
        all_results.update(h6)
    except Exception as e:
        logger.error("Temporal hypotheses group failed: %s", e, exc_info=True)

    # Группа 7: ROI
    try:
        if turnover_data is not None:
            h7 = test_roi_hypotheses(models_daily_data, turnover_data)
            all_results.update(h7)
        else:
            for key in ('H7a', 'H7b'):
                all_results[key] = _make_result(
                    hypothesis=f"ROI hypothesis {key}",
                    result='inconclusive',
                    p_value=None,
                    n_observations=0,
                    details={'reason': 'turnover_data не предоставлен'},
                )
    except Exception as e:
        logger.error("ROI hypotheses group failed: %s", e, exc_info=True)

    # Подсчёт итогов
    confirmed = sum(1 for r in all_results.values() if r.get('result') == 'confirmed')
    rejected = sum(1 for r in all_results.values() if r.get('result') == 'rejected')
    inconclusive = sum(1 for r in all_results.values() if r.get('result') == 'inconclusive')
    total = len(all_results)

    summary = (
        f"Из {total} гипотез подтверждено {confirmed}, "
        f"отвергнуто {rejected}, {inconclusive} неопределённых."
    )

    logger.info("Hypothesis testing complete: %s", summary)

    return {
        'tested_at': get_now_msk().isoformat(),
        'total_hypotheses': total,
        'confirmed': confirmed,
        'rejected': rejected,
        'inconclusive': inconclusive,
        'results': all_results,
        'summary': summary,
    }
