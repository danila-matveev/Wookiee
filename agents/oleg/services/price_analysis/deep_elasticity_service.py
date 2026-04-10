import logging
from datetime import timedelta
import pandas as pd
from typing import Dict, Any

from shared.data_layer import (
    _get_wb_connection,
    _get_ozon_connection,
    get_artikuly_statuses
)
from agents.oleg.services.time_utils import get_now_msk
from agents.oleg.services.price_analysis.regression_engine import estimate_price_elasticity

logger = logging.getLogger(__name__)

# Группировка статусов
STATUS_GROUPS = {
    'development': ['Продается', 'Новый', 'Запуск', 'План', 'Подготовка'],
    'liquidation': ['Выводим']
}

def _get_group_for_status(status: str) -> str:
    status = status.strip() if status else ""
    for group, statuses in STATUS_GROUPS.items():
        if status in statuses:
            return group
    return 'other'

def fetch_raw_orders_wb(start_date: str, end_date: str, model_osnova: str) -> pd.DataFrame:
    """Загрузка сырых данных по заказам WB для поартикульного анализа."""
    conn = _get_wb_connection()
    cur = conn.cursor()
    
    query = """
    SELECT 
        date::date as dt,
        LOWER(supplierarticle) as article,
        COUNT(*) as orders_count,
        SUM(finishedprice::numeric) as sum_after_spp,
        SUM(pricewithdisc::numeric) as sum_before_spp
    FROM orders
    WHERE date >= %s AND date < %s
      AND LOWER(SPLIT_PART(supplierarticle, '/', 1)) = %s
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    cur.execute(query, (start_date, end_date, model_osnova.lower()))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return pd.DataFrame(rows, columns=['dt', 'article', 'orders_count', 'sum_after_spp', 'sum_before_spp'])

def fetch_raw_orders_ozon(start_date: str, end_date: str, model_osnova: str) -> pd.DataFrame:
    """Загрузка сырых данных по заказам Ozon для поартикульного анализа."""
    conn = _get_ozon_connection()
    cur = conn.cursor()
    
    # Ozon orders are in 'postings' table
    # price is the price after all discounts
    query = """
    SELECT 
        in_process_at::date as dt,
        LOWER(offer_id) as article,
        COUNT(*) as orders_count,
        SUM(price::numeric) as sum_after_spp,
        -- На Ozon нет явного разделения до/после СПП в postings в таком же виде как на WB,
        -- но мы берем price как 'после' и позже подтянем кабинетную цену как 'до'.
        SUM(price::numeric) as sum_before_spp 
    FROM postings
    WHERE in_process_at >= %s AND in_process_at < %s
      AND LOWER(offer_id) LIKE %s
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    # offer_id often starts with model_osnova/
    cur.execute(query, (start_date, end_date, f"{model_osnova.lower()}/%"))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return pd.DataFrame(rows, columns=['dt', 'article', 'orders_count', 'sum_after_spp', 'sum_before_spp'])

def analyze_model_deep_elasticity(channel: str, model_osnova: str, lookback_days: int = 180) -> Dict[str, Any]:
    """Полный цикл глубокого анализа эластичности по группам статусов SKU."""
    now_msk = get_now_msk()
    end_date = now_msk.strftime('%Y-%m-%d')
    start_date = (now_msk - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    
    # 1. Получаем статусы
    statuses = get_artikuly_statuses()
    
    # 2. Грузим заказы
    if channel == 'wb':
        df = fetch_raw_orders_wb(start_date, end_date, model_osnova)
    else:
        df = fetch_raw_orders_ozon(start_date, end_date, model_osnova)
        
    if df.empty:
        return {'error': f'No order data for {model_osnova} on {channel}'}

    # 3. Присваиваем группы
    df['status'] = df['article'].map(lambda x: statuses.get(x, 'Продается')) # по умолчанию 'Продается' если нет в базе
    df['group'] = df['status'].apply(_get_group_for_status)
    
    results = {
        'model': model_osnova,
        'channel': channel,
        'period': f"{start_date} - {end_date}",
        'groups': {}
    }

    for group_name in ['development', 'liquidation']:
        group_df = df[df['group'] == group_name].copy()
        if group_df.empty:
            continue
            
        # 4. First-Sale Alignment: для каждого SKU находим минимальную дату
        article_starts = group_df.groupby('article')['dt'].min()
        
        # 5. Синтетическая агрегация по дням
        # Чтобы не учитывать нули до начала продаж SKU, создаем 'чистую' таблицу спроса
        daily_agg = group_df.groupby('dt').agg({
            'orders_count': 'sum',
            'sum_after_spp': 'sum',
            'sum_before_spp': 'sum'
        }).reset_index()
        
        # Средневзвешенная цена дня (конвертируем в float для numpy/regression)
        daily_agg['price_per_unit'] = (daily_agg['sum_after_spp'] / daily_agg['orders_count']).apply(float)
        
        # Для эластичности нам нужен список dict с 'price_per_unit' и 'orders_count'
        analysis_data = daily_agg[['dt', 'price_per_unit', 'orders_count']].rename(columns={'dt': 'date'}).to_dict('records')
        
        # 6. Расчет эластичности
        elasticity_result = estimate_price_elasticity(analysis_data)
        
        # 7. Расчет текущего СПП (за последние 7 дней)
        recent_7 = daily_agg.sort_values('dt').tail(7)
        avg_spp = 0.0
        if not recent_7.empty and recent_7['sum_before_spp'].sum() > 0:
            avg_spp = (recent_7['sum_before_spp'].sum() - recent_7['sum_after_spp'].sum()) / recent_7['sum_before_spp'].sum()
        
        results['groups'][group_name] = {
            'elasticity': elasticity_result,
            'current_metrics': {
                'avg_price_after_spp': round(float(recent_7['price_per_unit'].mean()), 2) if not recent_7.empty else 0,
                'avg_spp_pct': round(float(avg_spp * 100), 2),
                'daily_orders': round(float(recent_7['orders_count'].mean()), 1) if not recent_7.empty else 0
            },
            'sku_count': group_df['article'].nunique(),
            'sku_list': group_df['article'].unique().tolist()
        }
        
    return results
