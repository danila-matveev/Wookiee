"""
Shared ABC-classification functions.

Used by both abc_analysis.py (per-channel) and abc_analysis_unified.py (merged).
"""
from statistics import median


def calc_abc_classes(articles_data):
    """
    ABC-classification by margin within each model.

    Input: list of dicts with keys: article, model, margin, ...
    Output: dict {article_lower: 'A'|'B'|'C'}
    """
    models = {}
    for a in articles_data:
        model = a['model']
        if model not in models:
            models[model] = []
        models[model].append(a)

    abc = {}
    for model, items in models.items():
        sorted_items = sorted(items, key=lambda x: x['margin'], reverse=True)
        total_margin = sum(x['margin'] for x in sorted_items)

        if total_margin <= 0:
            for item in sorted_items:
                abc[item['article'].lower()] = 'C'
            continue

        cumulative = 0
        for item in sorted_items:
            share = item['margin'] / total_margin if total_margin > 0 else 0
            cumulative += share

            if cumulative <= 0.80:
                abc[item['article'].lower()] = 'A'
            elif cumulative <= 0.95:
                abc[item['article'].lower()] = 'B'
            else:
                abc[item['article'].lower()] = 'C'

    return abc


def calc_high_turnover(articles_data, turnover_map):
    """
    Identify articles with high turnover within each model.

    Rule: turnover > 1.5 × model median.
    Input: articles_data — list of dicts, turnover_map — {article_lower: days}
    Output: dict {article_lower: True|False}
    """
    models = {}
    for a in articles_data:
        model = a['model']
        key = a['article'].lower()
        turn = turnover_map.get(key, 0)
        if model not in models:
            models[model] = []
        models[model].append((key, turn))

    result = {}
    for model, items in models.items():
        turnovers = [t for _, t in items if t > 0]
        if not turnovers:
            for key, _ in items:
                result[key] = False
            continue

        med = median(turnovers)
        threshold = med * 1.5

        for key, turn in items:
            result[key] = turn > threshold if turn > 0 else False

    return result


def classify_article(abc_last, abc_prev, high_turn_last, high_turn_prev,
                     status, margin, model_article_count):
    """
    Final article classification.

    Returns: (category, recommendation, reasons_list, dynamics)
    """
    # Priority 1: «Новый»
    if status in ('Новый', 'Запуск'):
        rec = status
        reasons = ['Статус: ' + status, 'Рано судить по метрикам']
        dynamics = 'Наблюдение'
        return 'Новый', rec, reasons, dynamics

    # ABC dynamics
    if abc_last == abc_prev:
        abc_stable = True
        abc_dynamic = 'устойчивый'
    elif abc_prev is None:
        abc_stable = False
        abc_dynamic = 'нет данных за пред. месяц'
    else:
        abc_stable = False
        if abc_last == 'C' and abc_prev != 'C':
            abc_dynamic = 'ухудшение (появился)'
        elif abc_last != 'C' and abc_prev == 'C':
            abc_dynamic = 'улучшение (появился)'
        else:
            abc_dynamic = 'изменился'

    # Turnover dynamics
    ht_last = high_turn_last or False
    ht_prev = high_turn_prev or False
    if ht_last and ht_prev:
        turn_signal = 'высокий оборот устойчиво'
    elif ht_last and not ht_prev:
        turn_signal = 'высокий оборот появился'
    else:
        turn_signal = ''

    # Category
    reasons = []
    small_model = model_article_count <= 2

    if abc_last == 'C':
        category = 'Неликвид'
        reasons.append('ABC = C (хвост маржи модели)')
        if ht_last:
            reasons.append('Оборот выше 1.5× медианы')
        if margin <= 0:
            reasons.append('Маржа отрицательная')

        if abc_stable and ht_last and ht_prev:
            dynamics = 'Устойчивый: C в обоих мес., оборот высокий'
        elif abc_stable:
            dynamics = 'Устойчивый: C в обоих мес.'
        elif abc_prev == 'C':
            dynamics = 'Устойчивый: C в обоих мес.'
        else:
            dynamics = f'Появился: {abc_dynamic}'

        if status == 'Выводим':
            rec = 'Выводим'
            reasons.insert(0, 'Статус подтверждён')
        elif status == 'Продается':
            rec = 'Выводим'
            reasons.insert(0, 'Рекомендация: перевести в вывод')
        else:
            rec = 'Выводим'

    elif abc_last == 'A':
        category = 'Лучшие'
        reasons.append('ABC = A (ТОП-80% маржи модели)')
        if ht_last:
            reasons.append('Внимание: высокий оборот')
            if ht_prev:
                category = 'Хорошие'
                reasons[0] = 'ABC = A, но высокий оборот устойчиво'

        if abc_stable:
            dynamics = 'Устойчивый: A в обоих мес.'
        elif abc_prev is None:
            dynamics = 'Нет данных за пред. месяц'
        else:
            dynamics = f'Появился: был {abc_prev}'

        if status in ('Продается', 'Выводим', None):
            rec = 'Продаются'
            if status == 'Продается':
                reasons.insert(0, 'Статус подтверждён')
        else:
            rec = 'Продаются'

    else:  # B
        category = 'Хорошие'
        reasons.append('ABC = B (80-95% маржи модели)')
        if ht_last:
            reasons.append('Внимание: высокий оборот')

        if abc_stable:
            dynamics = 'Устойчивый: B в обоих мес.'
        elif abc_prev is None:
            dynamics = 'Нет данных за пред. месяц'
        else:
            dynamics = f'Появился: был {abc_prev}'

        if status == 'Продается':
            rec = 'Продаются'
            reasons.insert(0, 'Статус подтверждён')
        elif status == 'Выводим':
            rec = 'Продаются'
            reasons.insert(0, 'Внимание: статус «Выводим», но метрики хорошие')
        else:
            rec = 'Продаются'

    if small_model:
        reasons.append('Мало артикулов в модели, вывод условный')

    if turn_signal and turn_signal not in dynamics:
        dynamics += f'; {turn_signal}'

    return category, rec, reasons, dynamics
