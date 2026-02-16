#!/usr/bin/env python3
"""
Evaluation script: measures accuracy of price recommendations.

Reads from LearningStore (SQLite) and calculates:
- MAPE for margin predictions
- MAPE for volume predictions
- Direction accuracy (predicted direction matches actual)
- Breakdown by model, channel, confidence level

Usage:
    python scripts/evaluate_price_accuracy.py
    python scripts/evaluate_price_accuracy.py --weeks 4
    python scripts/evaluate_price_accuracy.py --db-path agents/oleg/data/reports.db
"""
import argparse
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.oleg.services.price_analysis.learning_store import LearningStore


def evaluate(store: LearningStore, weeks: int = 4):
    """Run evaluation and print results."""
    cutoff = (datetime.now() - timedelta(weeks=weeks)).isoformat()

    # Get all checked recommendations
    conn = store._get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT id, model, channel, action, confidence,
           predicted_margin_impact, actual_margin_impact,
           predicted_volume_impact, actual_volume_impact,
           current_price, recommended_price, actual_price_after,
           created_at, user_feedback, user_rating
    FROM price_recommendations
    WHERE created_at > ?
    ORDER BY created_at DESC
    """, (cutoff,))

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not rows:
        print(f"No recommendations found in the last {weeks} weeks.")
        print("Run weekly_price_review a few times first, then wait for outcome_checker.")
        return

    checked = [r for r in rows if r['actual_margin_impact'] is not None]
    unchecked = [r for r in rows if r['actual_margin_impact'] is None]

    print(f"=== Оценка точности ценовых прогнозов ===")
    print(f"Период: последние {weeks} недель")
    print(f"Всего рекомендаций: {len(rows)}")
    print(f"С исходами: {len(checked)}")
    print(f"Без исходов: {len(unchecked)}")
    print()

    if not checked:
        print("Нет рекомендаций с проверенными исходами.")
        print("Подождите пока outcome_checker (Ср 09:00) проверит рекомендации старше 7 дней.\n")

        # Still show recommendations summary
        print("--- Все рекомендации ---")
        for r in rows:
            print(f"  [{r['created_at'][:10]}] {r['model']} ({r['channel']}): "
                  f"{r['action']}, confidence={r['confidence']}")
        return

    # Calculate MAPE
    margin_errors = []
    volume_errors = []
    direction_matches = 0
    direction_total = 0

    for r in checked:
        pred_m = r['predicted_margin_impact']
        act_m = r['actual_margin_impact']
        pred_v = r['predicted_volume_impact']
        act_v = r['actual_volume_impact']

        if pred_m is not None and act_m is not None and act_m != 0:
            margin_errors.append({
                'model': r['model'],
                'channel': r['channel'],
                'confidence': r['confidence'],
                'error_pct': abs(pred_m - act_m) / abs(act_m) * 100,
                'predicted': pred_m,
                'actual': act_m,
            })

        if pred_v is not None and act_v is not None and act_v != 0:
            volume_errors.append({
                'model': r['model'],
                'channel': r['channel'],
                'confidence': r['confidence'],
                'error_pct': abs(pred_v - act_v) / abs(act_v) * 100,
                'predicted': pred_v,
                'actual': act_v,
            })

        # Direction accuracy
        if pred_m is not None and act_m is not None:
            pred_dir = 'up' if pred_m > 0 else 'down' if pred_m < 0 else 'flat'
            act_dir = 'up' if act_m > 0 else 'down' if act_m < 0 else 'flat'
            direction_total += 1
            if pred_dir == act_dir:
                direction_matches += 1

    # Overall MAPE
    overall_margin_mape = (
        sum(e['error_pct'] for e in margin_errors) / len(margin_errors)
        if margin_errors else None
    )
    overall_volume_mape = (
        sum(e['error_pct'] for e in volume_errors) / len(volume_errors)
        if volume_errors else None
    )
    direction_accuracy = (
        direction_matches / direction_total * 100
        if direction_total > 0 else None
    )

    print("--- Общие метрики ---")
    if overall_margin_mape is not None:
        target = "OK" if overall_margin_mape < 20 else "ВЫШЕ ЦЕЛЕВОГО"
        print(f"  MAPE маржи: {overall_margin_mape:.1f}% (цель < 20%) [{target}]")
    if overall_volume_mape is not None:
        target = "OK" if overall_volume_mape < 25 else "ВЫШЕ ЦЕЛЕВОГО"
        print(f"  MAPE объёма: {overall_volume_mape:.1f}% (цель < 25%) [{target}]")
    if direction_accuracy is not None:
        target = "OK" if direction_accuracy >= 70 else "НИЖЕ ЦЕЛЕВОГО"
        print(f"  Direction accuracy: {direction_accuracy:.0f}% "
              f"({direction_matches}/{direction_total}) (цель >= 70%) [{target}]")
    print()

    # By model
    models = set(e['model'] for e in margin_errors)
    if models:
        print("--- По моделям ---")
        for model in sorted(models):
            m_errors = [e for e in margin_errors if e['model'] == model]
            v_errors = [e for e in volume_errors if e['model'] == model]
            m_mape = sum(e['error_pct'] for e in m_errors) / len(m_errors) if m_errors else None
            v_mape = sum(e['error_pct'] for e in v_errors) / len(v_errors) if v_errors else None
            channel = m_errors[0]['channel'] if m_errors else '?'
            parts = [f"{model} ({channel}):"]
            if m_mape is not None:
                parts.append(f"MAPE маржи {m_mape:.1f}%")
            if v_mape is not None:
                parts.append(f"MAPE объёма {v_mape:.1f}%")
            parts.append(f"n={len(m_errors)}")
            print(f"  {', '.join(parts)}")
        print()

    # By confidence
    confidences = set(e['confidence'] for e in margin_errors)
    if confidences:
        print("--- По confidence ---")
        for conf in ['high', 'medium', 'low']:
            c_errors = [e for e in margin_errors if e['confidence'] == conf]
            if c_errors:
                c_mape = sum(e['error_pct'] for e in c_errors) / len(c_errors)
                print(f"  {conf}: MAPE маржи {c_mape:.1f}% (n={len(c_errors)})")
        print()

    # Feedback summary
    with_feedback = [r for r in checked if r['user_feedback']]
    if with_feedback:
        print("--- Обратная связь ---")
        for r in with_feedback:
            rating = f"⭐{r['user_rating']}" if r['user_rating'] else ""
            print(f"  [{r['created_at'][:10]}] {r['model']}: "
                  f"{r['user_feedback'][:80]} {rating}")
        print()

    # Save report
    reports_dir = ROOT / 'reports'
    reports_dir.mkdir(exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')

    report = {
        'evaluation_date': today,
        'period_weeks': weeks,
        'total_recommendations': len(rows),
        'checked_recommendations': len(checked),
        'overall_margin_mape': round(overall_margin_mape, 1) if overall_margin_mape else None,
        'overall_volume_mape': round(overall_volume_mape, 1) if overall_volume_mape else None,
        'direction_accuracy_pct': round(direction_accuracy, 1) if direction_accuracy else None,
        'direction_matches': direction_matches,
        'direction_total': direction_total,
        'by_model': {
            model: {
                'margin_mape': round(
                    sum(e['error_pct'] for e in margin_errors if e['model'] == model) /
                    max(1, len([e for e in margin_errors if e['model'] == model])), 1
                ),
                'n': len([e for e in margin_errors if e['model'] == model]),
            }
            for model in models
        } if models else {},
    }

    report_path = reports_dir / f'price_accuracy_{today}.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Отчёт сохранён: {report_path}")


def main():
    parser = argparse.ArgumentParser(description='Evaluate price prediction accuracy')
    parser.add_argument('--weeks', type=int, default=4, help='Lookback period in weeks')
    parser.add_argument('--db-path', default=None,
                        help='Path to SQLite DB (default: agents/oleg/data/reports.db)')
    args = parser.parse_args()

    db_path = args.db_path or str(ROOT / 'agents' / 'oleg' / 'data' / 'reports.db')

    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        print("Run the bot first to create the database, then try again.")
        sys.exit(1)

    store = LearningStore(db_path=db_path)
    evaluate(store, weeks=args.weeks)


if __name__ == '__main__':
    main()
