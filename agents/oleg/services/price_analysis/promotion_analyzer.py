"""
Promotion Analyzer — анализ акций WB/OZON и рекомендации по участию.

Алгоритм:
1. Получить список акций через API МП
2. Для каждой акции рассчитать маржу при акционной цене
3. Оценить подъём объёма на основе исторических данных
4. Вычислить чистый эффект на маржинальную прибыль
5. Рекомендовать участие/отказ
"""
import logging
from datetime import datetime, timedelta
from agents.oleg.services.time_utils import get_now_msk
from typing import Optional

import numpy as np
import pandas as pd

from shared.data_layer import (
    get_wb_price_margin_daily,
    get_ozon_price_margin_daily,
)

logger = logging.getLogger(__name__)

# Средний исторический подъём объёма при участии в акциях
# (начальные значения; learning_store обновит по факту)
DEFAULT_VOLUME_LIFT_PCT = {
    'wb': 30.0,   # WB: средний подъём 30%
    'ozon': 25.0, # OZON: средний подъём 25%
}


class PromotionAnalyzer:
    """Анализ акций маркетплейсов и рекомендации по участию."""

    def __init__(self, wb_clients=None, ozon_clients=None):
        """
        Args:
            wb_clients: dict {cabinet_name: WBClient}
            ozon_clients: dict {cabinet_name: OzonClient}
        """
        self.wb_clients = wb_clients or {}
        self.ozon_clients = ozon_clients or {}

    def scan_promotions(self, channel: str) -> list[dict]:
        """Получить список доступных акций для канала."""
        if channel == 'wb':
            return self._scan_wb_promotions()
        elif channel == 'ozon':
            return self._scan_ozon_promotions()
        return []

    def _scan_wb_promotions(self) -> list[dict]:
        """Получить акции WB через Calendar API.

        Фильтрует: убирает auto-скидки, "Распродажа в счет долга", тесты.
        """
        all_promotions = []
        seen_ids = set()
        for name, client in self.wb_clients.items():
            try:
                promos = client.get_promotions_list()
                for p in promos:
                    pid = p.get('id')
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    # Фильтруем нерелевантные
                    ptype = p.get('type', '')
                    pname = (p.get('name') or '').lower()
                    if ptype == 'auto':
                        continue
                    if 'долг' in pname or 'тест' in pname:
                        continue
                    p['cabinet'] = name
                    p['channel'] = 'wb'
                    all_promotions.append(p)
            except Exception as e:
                logger.error(f"WB promotions scan failed for {name}: {e}")
        return all_promotions

    def _scan_ozon_promotions(self) -> list[dict]:
        """Получить акции OZON через API."""
        all_promotions = []
        for name, client in self.ozon_clients.items():
            try:
                promos = client.get_promotions()
                for p in promos:
                    p['cabinet'] = name
                    p['channel'] = 'ozon'
                all_promotions.extend(promos)
            except Exception as e:
                logger.error(f"OZON promotions scan failed for {name}: {e}")
        return all_promotions

    def analyze_promotion(
        self,
        promotion: dict,
        model_metrics: dict,
        elasticity: dict = None,
        historical_volume_lift: float = None,
    ) -> dict:
        """
        Анализ конкретной акции с расчётом финансового эффекта.

        Args:
            promotion: данные акции (id, name, dates, required_discount)
            model_metrics: текущие метрики модели (price, margin, volume)
            elasticity: результат estimate_price_elasticity (опционально)
            historical_volume_lift: исторический подъём объёма % (из learning_store)

        Returns:
            dict с рекомендацией и финансовым расчётом.
        """
        channel = promotion.get('channel', 'wb')

        # Текущие метрики
        current_price = model_metrics.get('avg_price_per_unit', 0)
        current_margin = model_metrics.get('margin', 0)
        current_margin_pct = model_metrics.get('margin_pct', 0)
        current_sales = model_metrics.get('sales_count', 0)
        current_revenue = model_metrics.get('revenue', 0)

        if current_price <= 0 or current_sales <= 0:
            return {
                'error': 'invalid_current_metrics',
                'promotion': promotion,
            }

        # Скидка акции
        required_discount_pct = promotion.get('required_discount', 0)
        if required_discount_pct <= 0:
            required_discount_pct = promotion.get('discount', 0)

        promotion_price = current_price * (1 - required_discount_pct / 100)

        # Маржа при акционной цене
        margin_per_unit = current_margin / current_sales if current_sales > 0 else 0
        price_delta = promotion_price - current_price  # отрицательный (скидка)
        new_margin_per_unit = margin_per_unit + price_delta

        # Ожидаемый подъём объёма
        if historical_volume_lift is not None:
            volume_lift_pct = historical_volume_lift
        elif elasticity and 'elasticity' in elasticity:
            # Через эластичность: %ΔQ = ε × (-скидка%)
            volume_lift_pct = abs(elasticity['elasticity'] * required_discount_pct)
        else:
            volume_lift_pct = DEFAULT_VOLUME_LIFT_PCT.get(channel, 25.0)

        expected_sales = current_sales * (1 + volume_lift_pct / 100)

        # Период акции
        promo_start = promotion.get('startDate', promotion.get('date_start', ''))
        promo_end = promotion.get('endDate', promotion.get('date_end', ''))
        try:
            days = (
                datetime.strptime(str(promo_end)[:10], '%Y-%m-%d')
                - datetime.strptime(str(promo_start)[:10], '%Y-%m-%d')
            ).days
        except (ValueError, TypeError):
            days = 7  # default

        days = max(days, 1)

        # Финансовый расчёт
        daily_margin_current = current_margin / max(days, 1) if current_margin else margin_per_unit * (current_sales / max(days, 1))
        daily_margin_promo = new_margin_per_unit * (expected_sales / max(days, 1))
        daily_margin_delta = daily_margin_promo - daily_margin_current
        total_impact = daily_margin_delta * days

        # Рекомендация
        recommendation = 'participate' if total_impact > 0 else 'skip'

        return {
            'promotion_id': promotion.get('id'),
            'promotion_name': promotion.get('name', promotion.get('title', '')),
            'channel': channel,
            'dates': f"{str(promo_start)[:10]} — {str(promo_end)[:10]}",
            'days': days,
            'required_discount_pct': required_discount_pct,
            'recommendation': recommendation,
            'financial_impact': {
                'current_price': round(current_price, 2),
                'promotion_price': round(promotion_price, 2),
                'current_margin_per_unit': round(margin_per_unit, 2),
                'promo_margin_per_unit': round(new_margin_per_unit, 2),
                'margin_per_unit_change': round(price_delta, 2),
                'expected_volume_lift_pct': round(volume_lift_pct, 2),
                'current_daily_sales': round(current_sales / max(days, 1), 1),
                'expected_daily_sales': round(expected_sales / max(days, 1), 1),
                'current_daily_margin': round(daily_margin_current, 0),
                'promo_daily_margin': round(daily_margin_promo, 0),
                'daily_margin_change': round(daily_margin_delta, 0),
                'total_period_impact': round(total_impact, 0),
            },
            'volume_lift_source': (
                'historical' if historical_volume_lift is not None
                else 'elasticity' if elasticity else 'default'
            ),
            'reasoning': _build_promo_reasoning(
                recommendation, required_discount_pct,
                volume_lift_pct, total_impact,
                margin_per_unit, new_margin_per_unit,
            ),
        }

    def analyze_all_promotions(
        self,
        channel: str,
        models_metrics: list[dict],
        elasticities: dict = None,
    ) -> list[dict]:
        """
        Сканировать и проанализировать все акции для канала.

        Args:
            channel: 'wb' или 'ozon'
            models_metrics: список метрик по моделям из get_*_price_margin_by_model_period()
            elasticities: dict {model_name: elasticity_result}

        Returns:
            Список рекомендаций по акциям.
        """
        promotions = self.scan_promotions(channel)
        if not promotions:
            return [{'info': f'No promotions found for {channel}'}]

        results = []
        for promo in promotions:
            promo_results = []
            for model_data in models_metrics:
                model_name = model_data.get('model', '')
                elasticity = (elasticities or {}).get(model_name)

                analysis = self.analyze_promotion(
                    promotion=promo,
                    model_metrics=model_data,
                    elasticity=elasticity,
                )
                analysis['model'] = model_name
                promo_results.append(analysis)

            results.append({
                'promotion': promo,
                'model_analyses': promo_results,
                'models_to_participate': [
                    r['model'] for r in promo_results
                    if r.get('recommendation') == 'participate'
                ],
                'models_to_skip': [
                    r['model'] for r in promo_results
                    if r.get('recommendation') == 'skip'
                ],
                'total_impact': sum(
                    r.get('financial_impact', {}).get('total_period_impact', 0)
                    for r in promo_results
                    if r.get('recommendation') == 'participate'
                ),
            })

        return results

    def analyze_promotion_historically(
        self,
        channel: str,
        model: str,
        lookback_days: int = 180,
    ) -> dict:
        """
        Анализ исторических акций через обнаружение снижений цены >10%.

        Ищет периоды в прошлом, когда цена падала >10%, и вычисляет
        фактический подъём объёма. Это калиброванный volume_lift.
        """
        now_msk = get_now_msk()
        end_date = now_msk.strftime('%Y-%m-%d')
        start_date = (now_msk - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        if channel == 'wb':
            data = get_wb_price_margin_daily(start_date, end_date, model)
        else:
            data = get_ozon_price_margin_daily(start_date, end_date, model)

        if not data or len(data) < 30:
            return {'error': 'insufficient_data', 'n_days': len(data) if data else 0}

        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Обнаружение снижений цены >10%
        df['price_pct_change'] = df['price_per_unit'].pct_change(7) * 100  # 7-day change
        promo_periods = df[df['price_pct_change'] < -10].index.tolist()

        if not promo_periods:
            return {
                'model': model,
                'channel': channel,
                'promo_periods_found': 0,
                'calibrated_volume_lift': None,
                'note': 'No price drops >10% found in the last {} days'.format(lookback_days),
            }

        volume_lifts = []
        for idx in promo_periods:
            if idx < 7 or idx >= len(df) - 7:
                continue
            before = df.iloc[idx - 7:idx]['sales_count'].mean()
            during = df.iloc[idx:idx + 7]['sales_count'].mean()
            if before > 0:
                lift = (during - before) / before * 100
                volume_lifts.append(lift)

        if not volume_lifts:
            return {
                'model': model,
                'channel': channel,
                'promo_periods_found': len(promo_periods),
                'calibrated_volume_lift': None,
                'note': 'Promo periods found but insufficient surrounding data',
            }

        avg_lift = float(np.mean(volume_lifts))
        median_lift = float(np.median(volume_lifts))

        return {
            'model': model,
            'channel': channel,
            'promo_periods_found': len(volume_lifts),
            'calibrated_volume_lift': round(avg_lift, 1),
            'median_volume_lift': round(median_lift, 1),
            'min_lift': round(min(volume_lifts), 1),
            'max_lift': round(max(volume_lifts), 1),
            'lookback_days': lookback_days,
        }

    def generate_promotion_participation_plan(
        self,
        channel: str,
        models_metrics: list[dict],
        stock_data: dict = None,
        turnover_data: dict = None,
        elasticities: dict = None,
    ) -> dict:
        """
        Полный план участия в акциях с учётом остатков и оборачиваемости.

        Args:
            channel: 'wb' or 'ozon'
            models_metrics: list[dict] с метриками моделей
            stock_data: dict {model: {weeks_supply, status, ...}} (опционально)
            turnover_data: dict {model: {turnover_days, ...}} (опционально)
            elasticities: dict {model: {elasticity, ...}} (опционально)

        Returns:
            dict с models_to_participate, models_to_skip, net_impact
        """
        participate = []
        skip = []
        total_net_impact = 0

        for m in models_metrics:
            model_name = m.get('model', '')
            margin_pct = m.get('margin_pct', 0)
            sales_count = m.get('sales_count', 0)
            price = m.get('avg_price_per_unit', 0)

            stock_info = (stock_data or {}).get(model_name, {})
            turnover_info = (turnover_data or {}).get(model_name, {})
            elasticity_info = (elasticities or {}).get(model_name, {})

            stock_status = stock_info.get('status', 'healthy')
            weeks_supply = stock_info.get('weeks_supply')
            turnover_days = turnover_info.get('turnover_days', 0)

            # Правило 1: низкий запас → не участвуем
            if stock_status in ('critical_low', 'low'):
                skip.append({
                    'model': model_name,
                    'reason': f'Низкий запас ({weeks_supply} нед.) — акция ускорит вымывание',
                    'stock_status': stock_status,
                })
                continue

            # Правило 2: переизбыток → участвуем для ускорения оборота
            if stock_status in ('overstocked', 'severely_overstocked'):
                participate.append({
                    'model': model_name,
                    'reason': f'Затоваривание ({weeks_supply} нед.) — акция ускорит оборот',
                    'stock_status': stock_status,
                    'priority': 'high',
                    'estimated_impact': 'positive (clearing stock)',
                })
                continue

            # Правило 3: здоровый запас → решение по марже
            if margin_pct < 20:
                skip.append({
                    'model': model_name,
                    'reason': f'Низкая маржа ({margin_pct:.1f}%) — акция может привести к убыткам',
                    'stock_status': stock_status,
                })
                continue

            # Используем эластичность для оценки
            e = elasticity_info.get('elasticity')
            if e is not None and abs(e) > 1.5:
                # Elastic demand: promo effective
                participate.append({
                    'model': model_name,
                    'reason': f'Эластичный спрос (ε={e:.2f}) — акция даст значительный рост объёма',
                    'stock_status': stock_status,
                    'priority': 'medium',
                    'estimated_impact': f'volume +{abs(e) * 15:.0f}% at -15% discount',
                })
            elif margin_pct > 30:
                participate.append({
                    'model': model_name,
                    'reason': f'Высокая маржа ({margin_pct:.1f}%) — есть запас для скидки',
                    'stock_status': stock_status,
                    'priority': 'low',
                    'estimated_impact': 'moderate',
                })
            else:
                skip.append({
                    'model': model_name,
                    'reason': f'Недостаточно данных для обоснования участия',
                    'stock_status': stock_status,
                })

        return {
            'channel': channel,
            'models_to_participate': participate,
            'models_to_skip': skip,
            'participate_count': len(participate),
            'skip_count': len(skip),
            'total_models': len(models_metrics),
            'summary': (
                f"Из {len(models_metrics)} моделей: "
                f"{len(participate)} рекомендуется включить в акцию, "
                f"{len(skip)} — исключить."
            ),
        }


    def analyze_promotion_by_article(
        self,
        channel: str,
        promotion: dict,
        article_metrics: dict,
        nm_to_article: dict,
        volume_lift_pct: float = None,
        article_statuses: dict = None,
    ) -> dict:
        """
        Анализ акции на уровне артикулов.

        Args:
            channel: 'wb' или 'ozon'
            promotion: данные акции (id, name, dates, etc.)
            article_metrics: {article_lower: {sales_count, margin, revenue, ...}}
            nm_to_article: {nm_id: article_lower} из Supabase
            volume_lift_pct: ожидаемый подъём объёма (если None — дефолт)
            article_statuses: {article_lower: status} из get_artikuly_statuses()

        Returns:
            dict с артикульным анализом и summary.
        """
        promo_id = promotion.get('id')
        promo_name = promotion.get('name', promotion.get('title', 'Без названия'))
        required_discount_pct = promotion.get('required_discount', 0)
        if required_discount_pct <= 0:
            required_discount_pct = promotion.get('discount', 0)
        # WB calendar API не возвращает скидку — используем типичную 15%
        if required_discount_pct <= 0:
            required_discount_pct = 15.0

        if volume_lift_pct is None:
            volume_lift_pct = DEFAULT_VOLUME_LIFT_PCT.get(channel, 25.0)

        # WB API возвращает startDateTime/endDateTime, другие — startDate/date_start
        promo_start = (
            promotion.get('startDateTime')
            or promotion.get('startDate')
            or promotion.get('date_start', '')
        )
        promo_end = (
            promotion.get('endDateTime')
            or promotion.get('endDate')
            or promotion.get('date_end', '')
        )
        try:
            days = (
                datetime.strptime(str(promo_end)[:10], '%Y-%m-%d')
                - datetime.strptime(str(promo_start)[:10], '%Y-%m-%d')
            ).days
        except (ValueError, TypeError):
            days = 7
        days = max(days, 1)

        # Вычислить urgency
        try:
            start_dt = datetime.strptime(str(promo_start)[:10], '%Y-%m-%d').date()
            days_until = (start_dt - get_now_msk().date()).days
        except (ValueError, TypeError):
            days_until = 999

        if days_until <= 2:
            urgency = 'СРОЧНО'
        elif days_until <= 5:
            urgency = 'СКОРО'
        else:
            urgency = 'ПЛАНОВО'

        # Построить обратный маппинг article→nm_id один раз
        article_to_nm = {}
        for nm, art in nm_to_article.items():
            article_to_nm[art] = nm

        if article_statuses is None:
            article_statuses = {}

        # Анализируем все артикулы с продажами
        articles_analysis = []
        for article_lower, metrics in article_metrics.items():
            if metrics.get('sales_count', 0) <= 0:
                continue
            nm_id = article_to_nm.get(article_lower)
            analysis = self._analyze_single_article(
                article_lower, metrics, required_discount_pct,
                volume_lift_pct, days, nm_id,
            )
            analysis['status'] = article_statuses.get(article_lower, 'Продается')
            articles_analysis.append(analysis)

        # Классификация: participate / clearance (выводимые) / skip
        participate = [a for a in articles_analysis if a['recommendation'] == 'participate']
        clearance = [
            a for a in articles_analysis
            if a['recommendation'] == 'skip' and a.get('status') == 'Выводим'
        ]
        skip = [
            a for a in articles_analysis
            if a['recommendation'] == 'skip' and a.get('status') != 'Выводим'
        ]
        participate.sort(key=lambda x: x['total_impact'], reverse=True)
        clearance.sort(key=lambda x: x.get('current_daily_sales', 0), reverse=True)
        skip.sort(key=lambda x: x.get('breakeven_discount', 0), reverse=True)

        total_positive = sum(a['total_impact'] for a in participate)
        total_negative = sum(a['total_impact'] for a in skip)
        clearance_impact = sum(a['total_impact'] for a in clearance)

        return {
            'promotion': {
                'id': promo_id,
                'name': promo_name,
                'dates': f"{str(promo_start)[:10]} — {str(promo_end)[:10]}",
                'days': days,
                'discount_pct': required_discount_pct,
                'urgency': urgency,
                'days_until_start': days_until,
            },
            'channel': channel,
            'matched_articles': len(articles_analysis),
            'participate': participate,
            'clearance': clearance,
            'skip': skip,
            'summary': {
                'participate_count': len(participate),
                'clearance_count': len(clearance),
                'skip_count': len(skip),
                'total_positive_impact': round(total_positive),
                'total_negative_impact': round(total_negative),
                'clearance_impact': round(clearance_impact),
                'net_impact': round(total_positive + total_negative),
            },
        }

    def _analyze_single_article(
        self,
        article: str,
        metrics: dict,
        discount_pct: float,
        volume_lift_pct: float,
        promo_days: int,
        nm_id: int = None,
    ) -> dict:
        """Финансовый анализ одного артикула при участии в акции."""
        sales = metrics.get('sales_count', 0)
        margin = metrics.get('margin', 0)
        revenue = metrics.get('revenue', 0)

        if sales <= 0 or revenue <= 0:
            return {
                'article': article,
                'nm_id': nm_id,
                'recommendation': 'skip',
                'total_impact': 0,
                'reasoning': 'Нет продаж за период',
            }

        price_per_unit = revenue / sales
        margin_per_unit = margin / sales
        daily_sales = sales / 30  # article_metrics за 30 дней

        promo_price = price_per_unit * (1 - discount_pct / 100)
        price_delta = promo_price - price_per_unit
        new_margin_per_unit = margin_per_unit + price_delta
        expected_daily_sales = daily_sales * (1 + volume_lift_pct / 100)

        daily_margin_current = daily_sales * margin_per_unit
        daily_margin_promo = expected_daily_sales * new_margin_per_unit
        daily_delta = daily_margin_promo - daily_margin_current
        total_impact = daily_delta * promo_days

        recommendation = 'participate' if total_impact > 0 else 'skip'

        # Безубыточная скидка: при какой скидке total_impact == 0
        # daily_margin_promo = (daily_sales*(1+lift)) * (margin_per_unit - price*d/100)
        # = daily_margin_current → решаем относительно d
        # (1+lift)*(margin_per_unit - price*d/100) = margin_per_unit
        # margin_per_unit - price*d/100 = margin_per_unit/(1+lift)
        # price*d/100 = margin_per_unit - margin_per_unit/(1+lift)
        # d = 100 * margin_per_unit * (1 - 1/(1+lift)) / price
        lift = volume_lift_pct / 100
        if price_per_unit > 0 and (1 + lift) > 0:
            breakeven_discount = 100 * margin_per_unit * (1 - 1 / (1 + lift)) / price_per_unit
        else:
            breakeven_discount = 0
        margin_pct = (margin_per_unit / price_per_unit * 100) if price_per_unit > 0 else 0

        reasoning = _build_article_reasoning(
            recommendation, article, discount_pct,
            margin_per_unit, new_margin_per_unit,
            volume_lift_pct, total_impact, promo_days,
        )

        return {
            'article': article,
            'nm_id': nm_id,
            'recommendation': recommendation,
            'current_price': round(price_per_unit),
            'promo_price': round(promo_price),
            'current_margin_per_unit': round(margin_per_unit),
            'promo_margin_per_unit': round(new_margin_per_unit),
            'margin_pct': round(margin_pct, 1),
            'breakeven_discount': round(breakeven_discount, 1),
            'current_daily_sales': round(daily_sales, 1),
            'expected_daily_sales': round(expected_daily_sales, 1),
            'daily_margin_change': round(daily_delta),
            'total_impact': round(total_impact),
            'volume_lift_pct': volume_lift_pct,
            'reasoning': reasoning,
        }


def _build_article_reasoning(
    recommendation: str,
    article: str,
    discount_pct: float,
    margin_before: float,
    margin_after: float,
    volume_lift_pct: float,
    total_impact: float,
    days: int,
) -> str:
    """Построить обоснование для артикула."""
    if margin_after <= 0:
        return (
            f"Скидка {discount_pct:.0f}% делает артикул убыточным "
            f"(маржа {margin_before:.0f}₽ → {margin_after:.0f}₽/шт)"
        )
    if recommendation == 'participate':
        return (
            f"маржа {margin_before:.0f}→{margin_after:.0f}₽/шт, "
            f"+{volume_lift_pct:.0f}% объём → +{total_impact:.0f}₽ за {days}д"
        )
    return (
        f"маржа {margin_before:.0f}→{margin_after:.0f}₽/шт, "
        f"+{volume_lift_pct:.0f}% объём недостаточно → {total_impact:.0f}₽ за {days}д"
    )


def format_promotion_report(analyses: list[dict], channel: str) -> str:
    """Форматирование компактного отчёта по акциям в Markdown.

    Структура:
    1. Сводная таблица всех акций (одна строка = одна акция)
    2. Выгодные для участия (если есть)
    3. Выводимые товары — кандидаты на распродажу через акцию
    4. Ближе всего к безубыточности — при меньшей скидке могут быть выгодны
    """
    from agents.oleg.services.time_utils import get_now_msk

    now = get_now_msk()
    md = f"# Анализ акций {channel.upper()} — {now.strftime('%d.%m.%Y')}\n\n"

    if not analyses:
        md += "Акций не обнаружено.\n"
        return md

    # --- Секция 1: Сводная таблица ---
    md += "## Сводка по акциям\n\n"
    md += (
        "> Скидка оценочная (~15%) — WB Calendar API не возвращает точный %. "
        "Реальная скидка может отличаться.\n\n"
    )
    md += "| Акция | Даты | Дней | Участв. | Выводимые | Пропуск | Эффект |\n"
    md += "|-------|------|------|---------|-----------|---------|--------|\n"
    for a in analyses:
        promo = a.get('promotion', {})
        s = a.get('summary', {})
        urgency = promo.get('urgency', '')
        badge = '🔴' if urgency == 'СРОЧНО' else '🟡' if urgency == 'СКОРО' else ''
        name = promo.get('name', '?')[:40]
        net = s.get('net_impact', 0)
        md += (
            f"| {badge}{name} "
            f"| {promo.get('dates', '?')} "
            f"| {promo.get('days', '?')} "
            f"| {s.get('participate_count', 0)} "
            f"| {s.get('clearance_count', 0)} "
            f"| {s.get('skip_count', 0)} "
            f"| {'+' if net > 0 else ''}{net:,.0f}₽ |\n"
        )
    md += "\n"

    # --- Собрать все артикулы со всех акций ---
    all_participate = []
    all_clearance = []
    all_near_breakeven = []
    for a in analyses:
        promo = a.get('promotion', {})
        promo_label = promo.get('name', '?')[:30]
        for art in a.get('participate', []):
            art['_promo'] = promo_label
            all_participate.append(art)
        for art in a.get('clearance', []):
            art['_promo'] = promo_label
            all_clearance.append(art)
        # Ближе всего к безубыточности: skip-артикулы с breakeven > 5%
        for art in a.get('skip', []):
            be = art.get('breakeven_discount', 0)
            if be >= 5.0:
                art['_promo'] = promo_label
                all_near_breakeven.append(art)

    # Дедупликация по артикулу (оставляем лучший эффект)
    def _dedup_by_article(items, key='total_impact', reverse=True):
        seen = {}
        for item in items:
            art = item['article']
            if art not in seen or (
                (reverse and item[key] > seen[art][key])
                or (not reverse and item[key] < seen[art][key])
            ):
                seen[art] = item
        result = list(seen.values())
        result.sort(key=lambda x: x[key], reverse=reverse)
        return result

    all_participate = _dedup_by_article(all_participate)
    all_clearance = _dedup_by_article(all_clearance, key='current_daily_sales')
    all_near_breakeven = _dedup_by_article(all_near_breakeven, key='breakeven_discount')

    # --- Секция 2: Выгодные для участия ---
    if all_participate:
        md += "---\n\n## Выгодно участвовать\n\n"
        md += "| Артикул | Акция | Цена → Акция | Маржа/шт | Эффект |\n"
        md += "|---------|-------|-------------|---------|--------|\n"
        for art in all_participate[:15]:
            md += (
                f"| {art['article']} "
                f"| {art['_promo']} "
                f"| {art['current_price']}→{art['promo_price']}₽ "
                f"| {art['current_margin_per_unit']}→{art['promo_margin_per_unit']}₽ "
                f"| +{art['total_impact']:,.0f}₽ |\n"
            )
        md += "\n"

    # --- Секция 3: Выводимые (clearance) ---
    if all_clearance:
        md += "---\n\n## Выводимые товары — кандидаты на распродажу\n\n"
        md += (
            "> Для выводимых товаров участие в акции стратегически полезно: "
            "ускоряет распродажу остатков, даже если маржа снижается.\n\n"
        )
        md += "| Артикул | Прод/день | Маржа сейчас | Маржа акция | Потеря/период |\n"
        md += "|---------|-----------|-------------|-------------|---------------|\n"
        for art in all_clearance[:15]:
            md += (
                f"| {art['article']} "
                f"| {art.get('current_daily_sales', 0):.1f} "
                f"| {art.get('current_margin_per_unit', 0)}₽ "
                f"| {art.get('promo_margin_per_unit', 0)}₽ "
                f"| {art['total_impact']:,.0f}₽ |\n"
            )
        if len(all_clearance) > 15:
            md += f"\n... и ещё {len(all_clearance) - 15} выводимых артикулов\n"
        md += "\n"

    # --- Секция 4: Ближе всего к безубыточности ---
    if all_near_breakeven:
        md += "---\n\n## Ближе всего к безубыточности\n\n"
        md += (
            "> Эти артикулы могут быть выгодны при скидке меньше 15%. "
            "Столбец «Безубыт.скидка» — максимальная скидка, при которой участие не убыточно.\n\n"
        )
        md += "| Артикул | Маржа% | Безубыт.скидка | Маржа/шт | Прод/день |\n"
        md += "|---------|--------|----------------|---------|----------|\n"
        for art in all_near_breakeven[:10]:
            be = art.get('breakeven_discount', 0)
            md += (
                f"| {art['article']} "
                f"| {art.get('margin_pct', 0):.0f}% "
                f"| {be:.1f}% "
                f"| {art.get('current_margin_per_unit', 0)}₽ "
                f"| {art.get('current_daily_sales', 0):.1f} |\n"
            )
        md += "\n"

    # --- Ничего не найдено ---
    if not all_participate and not all_clearance and not all_near_breakeven:
        md += (
            "---\n\n"
            "При оценочной скидке ~15% ни один артикул не выходит в плюс.\n"
            "Средняя маржа ассортимента (12-31%) недостаточна для компенсации "
            "потери цены даже при подъёме объёма +30%.\n\n"
            "**Рекомендация:** участвовать только выводимыми товарами "
            "для ускорения распродажи остатков.\n"
        )

    return md


def _build_promo_reasoning(
    recommendation: str,
    discount_pct: float,
    volume_lift_pct: float,
    total_impact: float,
    margin_before: float,
    margin_after: float,
) -> str:
    """Построить текстовое обоснование."""
    if recommendation == 'participate':
        return (
            f"Несмотря на скидку {discount_pct}% (маржа/шт: {margin_before:.0f}₽ → {margin_after:.0f}₽), "
            f"ожидаемый рост объёма +{volume_lift_pct:.0f}% компенсирует потери. "
            f"Чистый эффект: +{total_impact:.0f}₽ за период."
        )
    else:
        return (
            f"Скидка {discount_pct}% снижает маржу/шт с {margin_before:.0f}₽ до {margin_after:.0f}₽. "
            f"Ожидаемый рост объёма +{volume_lift_pct:.0f}% не компенсирует потери. "
            f"Чистый эффект: {total_impact:.0f}₽ за период."
        )
