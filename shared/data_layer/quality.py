"""Data quality validation functions."""

from __future__ import annotations

from shared.data_layer._connection import _get_wb_connection, to_float, format_num

__all__ = [
    'validate_wb_data_quality',
]


def validate_wb_data_quality(target_date):
    """
    Проверяет WB данные на известные проблемы качества.
    Возвращает dict с предупреждениями и корректировками маржи.

    Известные проблемы:
    - retention == deduction (дубликация пайплайна) → маржа занижена на SUM(deduction)
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    warnings = []
    margin_adjustment = 0.0

    # Проверка: retention == deduction в каждой строке
    cur.execute("""
    SELECT
        COUNT(*) as total_rows,
        COUNT(*) FILTER (WHERE retention = deduction AND retention != 0) as dup_rows,
        COUNT(*) FILTER (WHERE retention != 0 OR deduction != 0) as nonzero_rows,
        SUM(retention) as total_retention,
        SUM(deduction) as total_deduction
    FROM abc_date
    WHERE date = %s;
    """, (target_date,))
    row = cur.fetchone()

    total_rows = row[0]
    dup_rows = row[1]
    nonzero_rows = row[2]
    total_retention = to_float(row[3])
    total_deduction = to_float(row[4])

    if nonzero_rows > 0 and dup_rows == nonzero_rows and total_retention == total_deduction and total_retention > 0:
        margin_adjustment = total_deduction  # добавляем обратно дубль
        warnings.append({
            'type': 'retention_deduction_dup',
            'severity': 'CRITICAL',
            'message': f"retention == deduction ({format_num(total_retention)} руб) во всех {dup_rows} строках — дубликация пайплайна. Маржа скорректирована на +{format_num(margin_adjustment)} руб",
            'explanation': (
                'retention — удержания МП (возвраты/брак), deduction — вычеты (штрафы/корректировки). '
                'Одинаковые значения = баг ETL-пайплайна (один столбец скопирован в другой). '
                'Маржа занижена на SUM(deduction). Корректировка: +deduction к марже, deduction обнулён.'
            ),
            'etl_status': 'Требуется исправление на стороне ETL-пайплайна',
            'comparison_note': 'Предыдущий день проверен отдельно — если аналогичная проблема, тоже скорректирован',
            'adjustment': margin_adjustment,
        })

    cur.close()
    conn.close()

    return {'warnings': warnings, 'margin_adjustment': margin_adjustment}
