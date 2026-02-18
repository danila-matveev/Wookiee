"""
Learning Store — хранение рекомендаций, исходов и обратной связи.

SQLite таблицы в agents/oleg/data/reports.db:
- price_recommendations: все выданные рекомендации + факт + feedback
- promotion_recommendations: рекомендации по акциям + исходы
- model_elasticity_cache: кэш эластичностей
- learned_rules: выученные правила и корректировки
"""
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from agents.oleg.services.time_utils import get_now_msk, get_today_msk
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / 'data' / 'reports.db'


class LearningStore:
    """Хранение рекомендаций и обучение на результатах."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        """Создать таблицы если не существуют."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.executescript("""
        CREATE TABLE IF NOT EXISTS price_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            model TEXT NOT NULL,
            channel TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            action TEXT NOT NULL,
            current_price REAL,
            recommended_price REAL,
            change_pct REAL,
            predicted_margin_impact REAL,
            predicted_volume_impact REAL,
            confidence TEXT,
            reasoning TEXT,
            elasticity_used REAL,
            r_squared REAL,
            full_data TEXT,
            -- Outcome tracking
            implemented INTEGER DEFAULT NULL,
            implemented_at TIMESTAMP,
            actual_price_after REAL,
            actual_margin_impact REAL,
            actual_volume_impact REAL,
            outcome_period_start DATE,
            outcome_period_end DATE,
            outcome_checked INTEGER DEFAULT 0,
            -- Notion
            notion_page_id TEXT,
            -- Feedback
            user_feedback TEXT,
            user_rating INTEGER,
            feedback_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS promotion_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            channel TEXT NOT NULL,
            promotion_id TEXT,
            promotion_name TEXT,
            promotion_start DATE,
            promotion_end DATE,
            recommendation TEXT NOT NULL,
            predicted_net_impact REAL,
            models_affected TEXT,
            full_data TEXT,
            -- Outcome tracking
            actual_participated INTEGER DEFAULT NULL,
            actual_net_impact REAL,
            outcome_notes TEXT,
            notion_page_id TEXT,
            -- Feedback
            user_feedback TEXT,
            feedback_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS model_elasticity_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            model TEXT NOT NULL,
            channel TEXT NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            elasticity REAL,
            elasticity_se REAL,
            r_squared REAL,
            p_value REAL,
            n_observations INTEGER,
            is_significant INTEGER,
            full_result TEXT,
            UNIQUE(model, channel, period_start, period_end)
        );

        CREATE TABLE IF NOT EXISTS learned_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            rule_type TEXT NOT NULL,
            model TEXT,
            channel TEXT,
            rule_content TEXT NOT NULL,
            source TEXT NOT NULL,
            confidence REAL,
            active INTEGER DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_price_rec_model
            ON price_recommendations(model, channel);
        CREATE INDEX IF NOT EXISTS idx_price_rec_date
            ON price_recommendations(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_promo_rec_channel
            ON promotion_recommendations(channel, promotion_start);
        CREATE INDEX IF NOT EXISTS idx_elasticity_cache
            ON model_elasticity_cache(model, channel, computed_at DESC);

        CREATE TABLE IF NOT EXISTS hypothesis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            hypothesis_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            model TEXT,
            result TEXT NOT NULL,
            confidence REAL,
            n_observations INTEGER,
            p_value REAL,
            full_result TEXT
        );

        CREATE TABLE IF NOT EXISTS roi_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date DATE DEFAULT CURRENT_DATE,
            model TEXT NOT NULL,
            channel TEXT NOT NULL,
            margin_pct REAL,
            turnover_days REAL,
            annual_roi REAL,
            avg_stock REAL,
            daily_sales REAL,
            price_per_unit REAL,
            UNIQUE(model, channel, snapshot_date)
        );

        CREATE INDEX IF NOT EXISTS idx_hypothesis_id
            ON hypothesis_results(hypothesis_id, channel);
        CREATE INDEX IF NOT EXISTS idx_roi_snapshot
            ON roi_snapshots(model, channel, snapshot_date DESC);
        """)

        conn.commit()
        conn.close()

    # ─── Price Recommendations ────────────────────────────────────

    def save_recommendation(self, rec: dict) -> int:
        """Сохранить ценовую рекомендацию. Возвращает ID."""
        conn = self._get_conn()
        cur = conn.cursor()

        recommended = rec.get('recommended', {})
        elasticity = rec.get('elasticity', {})

        cur.execute("""
        INSERT INTO price_recommendations
            (model, channel, recommendation_type, action,
             current_price, recommended_price, change_pct,
             predicted_margin_impact, predicted_volume_impact,
             confidence, reasoning, elasticity_used, r_squared, full_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rec.get('model', ''),
            rec.get('channel', ''),
            'price_change',
            rec.get('action', 'hold'),
            rec.get('current_metrics', {}).get('price_per_unit'),
            recommended.get('new_price') if isinstance(recommended, dict) else None,
            recommended.get('price_change_pct') if isinstance(recommended, dict) else None,
            recommended.get('predicted_impact', {}).get('margin_rub_change_per_day')
                if isinstance(recommended, dict) else None,
            recommended.get('predicted_impact', {}).get('volume_change_pct')
                if isinstance(recommended, dict) else None,
            rec.get('confidence', 'low'),
            recommended.get('reasoning', '') if isinstance(recommended, dict) else '',
            elasticity.get('elasticity'),
            elasticity.get('r_squared'),
            json.dumps(rec, default=str, ensure_ascii=False),
        ))

        rec_id = cur.lastrowid
        conn.commit()
        conn.close()
        return rec_id

    def record_outcome(self, rec_id: int, outcomes: dict) -> None:
        """Записать фактический результат рекомендации."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
        UPDATE price_recommendations
        SET implemented = ?,
            actual_price_after = ?,
            actual_margin_impact = ?,
            actual_volume_impact = ?,
            outcome_period_start = ?,
            outcome_period_end = ?,
            outcome_checked = 1
        WHERE id = ?
        """, (
            outcomes.get('implemented'),
            outcomes.get('actual_price_after'),
            outcomes.get('actual_margin_impact'),
            outcomes.get('actual_volume_impact'),
            outcomes.get('period_start'),
            outcomes.get('period_end'),
            rec_id,
        ))

        conn.commit()
        conn.close()

    def record_feedback(
        self, rec_id: int, feedback: str, rating: int = None
    ) -> None:
        """Записать обратную связь."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
        UPDATE price_recommendations
        SET user_feedback = ?,
            user_rating = ?,
            feedback_at = ?
        WHERE id = ?
        """, (feedback, rating, get_now_msk().isoformat(), rec_id))

        conn.commit()
        conn.close()

    def get_recommendations(
        self,
        model: str = None,
        channel: str = None,
        last_n: int = 10,
    ) -> list[dict]:
        """Получить последние рекомендации."""
        conn = self._get_conn()
        cur = conn.cursor()

        query = "SELECT * FROM price_recommendations WHERE 1=1"
        params = []

        if model:
            query += " AND model = ?"
            params.append(model.lower())
        if channel:
            query += " AND channel = ?"
            params.append(channel)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(last_n)

        cur.execute(query, params)
        results = [dict(row) for row in cur.fetchall()]

        conn.close()
        return results

    def get_unchecked_recommendations(self, min_age_days: int = 7) -> list[dict]:
        """Рекомендации старше N дней без проверки исхода."""
        conn = self._get_conn()
        cur = conn.cursor()

        cutoff = (get_now_msk() - timedelta(days=min_age_days)).isoformat()

        cur.execute("""
        SELECT * FROM price_recommendations
        WHERE outcome_checked = 0
          AND created_at < ?
        ORDER BY created_at
        """, (cutoff,))

        results = [dict(row) for row in cur.fetchall()]
        conn.close()
        return results

    def get_prediction_accuracy(
        self, model: str = None, last_n: int = 20
    ) -> dict:
        """Расчёт точности прогнозов (MAPE)."""
        conn = self._get_conn()
        cur = conn.cursor()

        query = """
        SELECT predicted_margin_impact, actual_margin_impact,
               predicted_volume_impact, actual_volume_impact
        FROM price_recommendations
        WHERE outcome_checked = 1
          AND actual_margin_impact IS NOT NULL
        """
        params = []
        if model:
            query += " AND model = ?"
            params.append(model.lower())
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(last_n)

        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return {'error': 'no_checked_outcomes', 'n': 0}

        margin_errors = []
        volume_errors = []
        for row in rows:
            pred_m, act_m = row[0], row[1]
            pred_v, act_v = row[2], row[3]
            if pred_m is not None and act_m is not None and act_m != 0:
                margin_errors.append(abs(pred_m - act_m) / abs(act_m) * 100)
            if pred_v is not None and act_v is not None and act_v != 0:
                volume_errors.append(abs(pred_v - act_v) / abs(act_v) * 100)

        return {
            'n_checked': len(rows),
            'margin_mape': round(sum(margin_errors) / len(margin_errors), 1) if margin_errors else None,
            'volume_mape': round(sum(volume_errors) / len(volume_errors), 1) if volume_errors else None,
        }

    # ─── Elasticity Cache ─────────────────────────────────────────

    def get_elasticity_cached(
        self, model: str, channel: str, max_age_days: int = 30
    ) -> Optional[dict]:
        """Получить кэшированную эластичность."""
        conn = self._get_conn()
        cur = conn.cursor()

        cutoff = (get_now_msk() - timedelta(days=max_age_days)).isoformat()

        cur.execute("""
        SELECT full_result FROM model_elasticity_cache
        WHERE model = ? AND channel = ? AND computed_at > ?
        ORDER BY computed_at DESC LIMIT 1
        """, (model.lower(), channel, cutoff))

        row = cur.fetchone()
        conn.close()

        if row and row['full_result']:
            return json.loads(row['full_result'])
        return None

    def cache_elasticity(
        self,
        model: str,
        channel: str,
        result: dict,
        period_start: str,
        period_end: str,
    ) -> None:
        """Сохранить эластичность в кэш."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
        INSERT OR REPLACE INTO model_elasticity_cache
            (model, channel, period_start, period_end,
             elasticity, elasticity_se, r_squared, p_value,
             n_observations, is_significant, full_result)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model.lower(),
            channel,
            period_start,
            period_end,
            result.get('elasticity'),
            result.get('elasticity_se'),
            result.get('r_squared'),
            result.get('p_value'),
            result.get('n_observations'),
            1 if result.get('is_significant') else 0,
            json.dumps(result, default=str, ensure_ascii=False),
        ))

        conn.commit()
        conn.close()

    # ─── Promotion Recommendations ────────────────────────────────

    def save_promotion_recommendation(self, rec: dict) -> int:
        """Сохранить рекомендацию по акции."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO promotion_recommendations
            (channel, promotion_id, promotion_name,
             promotion_start, promotion_end,
             recommendation, predicted_net_impact,
             models_affected, full_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rec.get('channel', ''),
            str(rec.get('promotion_id', '')),
            rec.get('promotion_name', ''),
            rec.get('promotion_start'),
            rec.get('promotion_end'),
            rec.get('recommendation', ''),
            rec.get('predicted_net_impact'),
            json.dumps(rec.get('models_affected', []), ensure_ascii=False),
            json.dumps(rec, default=str, ensure_ascii=False),
        ))

        rec_id = cur.lastrowid
        conn.commit()
        conn.close()
        return rec_id

    # ─── Learned Rules ────────────────────────────────────────────

    def save_learned_rule(self, rule: dict) -> int:
        """Сохранить выученное правило."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO learned_rules
            (rule_type, model, channel, rule_content, source, confidence)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            rule.get('rule_type', 'unknown'),
            rule.get('model'),
            rule.get('channel'),
            json.dumps(rule.get('content', {}), ensure_ascii=False),
            rule.get('source', 'manual'),
            rule.get('confidence', 0.5),
        ))

        rule_id = cur.lastrowid
        conn.commit()
        conn.close()
        return rule_id

    def get_active_rules(
        self, model: str = None, channel: str = None
    ) -> list[dict]:
        """Получить активные правила."""
        conn = self._get_conn()
        cur = conn.cursor()

        query = "SELECT * FROM learned_rules WHERE active = 1"
        params = []

        if model:
            query += " AND (model = ? OR model IS NULL)"
            params.append(model.lower())
        if channel:
            query += " AND (channel = ? OR channel IS NULL)"
            params.append(channel)

        query += " ORDER BY confidence DESC"
        cur.execute(query, params)
        results = [dict(row) for row in cur.fetchall()]

        conn.close()
        return results

    # ─── Hypothesis Results ───────────────────────────────────────

    def save_hypothesis_result(self, hypothesis_id: str, channel: str, result: dict, model: str = None) -> int:
        """Сохранить результат проверки гипотезы."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO hypothesis_results
            (hypothesis_id, channel, model, result, confidence, n_observations, p_value, full_result)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hypothesis_id,
            channel,
            model,
            result.get('result', 'inconclusive'),
            result.get('confidence'),
            result.get('n_observations'),
            result.get('p_value'),
            json.dumps(result, default=str, ensure_ascii=False),
        ))

        rec_id = cur.lastrowid
        conn.commit()
        conn.close()
        return rec_id

    def get_hypothesis_history(self, hypothesis_id: str = None, channel: str = None, last_n: int = 10) -> list[dict]:
        """Получить историю результатов проверки гипотез."""
        conn = self._get_conn()
        cur = conn.cursor()

        query = "SELECT * FROM hypothesis_results WHERE 1=1"
        params = []

        if hypothesis_id:
            query += " AND hypothesis_id = ?"
            params.append(hypothesis_id)
        if channel:
            query += " AND channel = ?"
            params.append(channel)

        query += " ORDER BY tested_at DESC LIMIT ?"
        params.append(last_n)

        cur.execute(query, params)
        results = [dict(row) for row in cur.fetchall()]

        conn.close()
        return results

    # ─── ROI Snapshots ────────────────────────────────────────────

    def save_roi_snapshot(self, model: str, channel: str, snapshot: dict) -> None:
        """Сохранить снапшот ROI модели."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
        INSERT OR REPLACE INTO roi_snapshots
            (model, channel, margin_pct, turnover_days, annual_roi,
             avg_stock, daily_sales, price_per_unit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model.lower(),
            channel,
            snapshot.get('margin_pct'),
            snapshot.get('turnover_days'),
            snapshot.get('annual_roi'),
            snapshot.get('avg_stock'),
            snapshot.get('daily_sales'),
            snapshot.get('price_per_unit'),
        ))

        conn.commit()
        conn.close()

    def get_roi_trend(self, model: str, channel: str, last_n: int = 12) -> list[dict]:
        """Получить тренд ROI модели (последние N снапшотов)."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
        SELECT * FROM roi_snapshots
        WHERE model = ? AND channel = ?
        ORDER BY snapshot_date DESC LIMIT ?
        """, (model.lower(), channel, last_n))

        results = [dict(row) for row in cur.fetchall()]
        conn.close()
        return results
