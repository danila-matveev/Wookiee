"""
Tests for learning_store.py — SQLite persistence for recommendations and outcomes.
"""
import json
import pytest
from datetime import datetime, timedelta

from agents.oleg.services.price_analysis.learning_store import LearningStore


@pytest.fixture
def store(tmp_path):
    """Fresh LearningStore with isolated temp database."""
    db_path = str(tmp_path / "test_reports.db")
    return LearningStore(db_path=db_path)


@pytest.fixture
def sample_recommendation():
    """Sample recommendation dict as produced by recommendation_engine."""
    return {
        'model': 'wendy',
        'channel': 'wb',
        'action': 'increase_price',
        'current_metrics': {
            'price_per_unit': 2500.0,
            'sales_per_day': 50.0,
            'margin_per_day': 25000.0,
            'margin_pct': 22.0,
            'revenue_per_day': 125000.0,
        },
        'elasticity': {
            'elasticity': -0.5,
            'r_squared': 0.65,
            'p_value': 0.01,
            'is_significant': True,
        },
        'confidence': 'high',
        'recommended': {
            'price_change_pct': 5.0,
            'new_price': 2625.0,
            'predicted_impact': {
                'margin_rub_change_per_day': 3000.0,
                'margin_pct_change': 1.2,
                'volume_change_pct': -2.5,
                'revenue_change_pct': 2.3,
            },
            'reasoning': 'Test reasoning',
        },
        'scenarios': [],
        'risk_factors': [],
    }


class TestSaveAndRetrieve:
    def test_save_returns_id(self, store, sample_recommendation):
        rec_id = store.save_recommendation(sample_recommendation)
        assert isinstance(rec_id, int)
        assert rec_id > 0

    def test_retrieve_saved(self, store, sample_recommendation):
        rec_id = store.save_recommendation(sample_recommendation)
        recs = store.get_recommendations(model='wendy')
        assert len(recs) >= 1
        found = next((r for r in recs if r['id'] == rec_id), None)
        assert found is not None
        assert found['model'] == 'wendy'
        assert found['channel'] == 'wb'
        assert found['action'] == 'increase_price'
        assert found['confidence'] == 'high'

    def test_retrieve_by_channel(self, store, sample_recommendation):
        store.save_recommendation(sample_recommendation)
        recs = store.get_recommendations(channel='wb')
        assert len(recs) >= 1
        assert all(r['channel'] == 'wb' for r in recs)

    def test_limit(self, store, sample_recommendation):
        for _ in range(5):
            store.save_recommendation(sample_recommendation)
        recs = store.get_recommendations(last_n=3)
        assert len(recs) == 3


class TestRecordOutcome:
    def test_outcome_saves(self, store, sample_recommendation):
        rec_id = store.save_recommendation(sample_recommendation)
        store.record_outcome(rec_id, {
            'implemented': 1,
            'actual_price_after': 2625.0,
            'actual_margin_impact': 2800.0,
            'actual_volume_impact': -3.0,
            'period_start': '2026-02-01',
            'period_end': '2026-02-08',
        })
        recs = store.get_recommendations(model='wendy')
        updated = next(r for r in recs if r['id'] == rec_id)
        assert updated['outcome_checked'] == 1
        assert updated['actual_margin_impact'] == 2800.0
        assert updated['implemented'] == 1

    def test_unchecked_recommendations(self, store, sample_recommendation):
        rec_id = store.save_recommendation(sample_recommendation)
        # Manually backdate created_at
        conn = store._get_conn()
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        conn.execute(
            "UPDATE price_recommendations SET created_at = ? WHERE id = ?",
            (old_date, rec_id)
        )
        conn.commit()
        conn.close()

        unchecked = store.get_unchecked_recommendations(min_age_days=7)
        assert len(unchecked) >= 1
        assert any(r['id'] == rec_id for r in unchecked)

    def test_checked_not_in_unchecked(self, store, sample_recommendation):
        rec_id = store.save_recommendation(sample_recommendation)
        store.record_outcome(rec_id, {'actual_margin_impact': 100})

        # Backdate
        conn = store._get_conn()
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        conn.execute(
            "UPDATE price_recommendations SET created_at = ? WHERE id = ?",
            (old_date, rec_id)
        )
        conn.commit()
        conn.close()

        unchecked = store.get_unchecked_recommendations(min_age_days=7)
        assert not any(r['id'] == rec_id for r in unchecked)


class TestRecordFeedback:
    def test_feedback_saves(self, store, sample_recommendation):
        rec_id = store.save_recommendation(sample_recommendation)
        store.record_feedback(rec_id, feedback="Good recommendation", rating=5)
        recs = store.get_recommendations(model='wendy')
        updated = next(r for r in recs if r['id'] == rec_id)
        assert updated['user_feedback'] == "Good recommendation"
        assert updated['user_rating'] == 5
        assert updated['feedback_at'] is not None


class TestPredictionAccuracy:
    def test_mape_calculation(self, store, sample_recommendation):
        # Save two recommendations with outcomes
        for i in range(2):
            rec_id = store.save_recommendation(sample_recommendation)
            store.record_outcome(rec_id, {
                'actual_margin_impact': 2500.0 + i * 200,  # vary slightly
                'actual_volume_impact': -2.0 - i * 0.5,
            })

        accuracy = store.get_prediction_accuracy(model='wendy')
        assert 'error' not in accuracy
        assert accuracy['n_checked'] == 2
        assert accuracy['margin_mape'] is not None
        assert accuracy['margin_mape'] >= 0

    def test_no_outcomes(self, store):
        accuracy = store.get_prediction_accuracy()
        assert accuracy['error'] == 'no_checked_outcomes'
        assert accuracy['n'] == 0


class TestElasticityCache:
    def test_cache_and_retrieve(self, store):
        result = {
            'elasticity': -0.7,
            'r_squared': 0.55,
            'p_value': 0.02,
            'is_significant': True,
            'n_observations': 30,
        }
        store.cache_elasticity('wendy', 'wb', result, '2026-01-01', '2026-01-30')
        cached = store.get_elasticity_cached('wendy', 'wb')
        assert cached is not None
        assert cached['elasticity'] == -0.7
        assert cached['r_squared'] == 0.55

    def test_stale_cache_returns_none(self, store):
        result = {'elasticity': -0.5, 'r_squared': 0.4}
        store.cache_elasticity('ruby', 'ozon', result, '2025-01-01', '2025-01-30')
        # Backdate computed_at
        conn = store._get_conn()
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        conn.execute(
            "UPDATE model_elasticity_cache SET computed_at = ? WHERE model = 'ruby'",
            (old_date,)
        )
        conn.commit()
        conn.close()

        cached = store.get_elasticity_cached('ruby', 'ozon', max_age_days=30)
        assert cached is None

    def test_cache_respects_channel(self, store):
        result = {'elasticity': -0.5, 'r_squared': 0.4}
        store.cache_elasticity('wendy', 'wb', result, '2026-01-01', '2026-01-30')
        # Query for different channel
        cached = store.get_elasticity_cached('wendy', 'ozon')
        assert cached is None


class TestEmptyDatabase:
    def test_empty_recommendations(self, store):
        recs = store.get_recommendations()
        assert recs == []

    def test_empty_unchecked(self, store):
        unchecked = store.get_unchecked_recommendations()
        assert unchecked == []

    def test_empty_accuracy(self, store):
        accuracy = store.get_prediction_accuracy()
        assert accuracy['error'] == 'no_checked_outcomes'

    def test_empty_cache(self, store):
        cached = store.get_elasticity_cached('nonexistent', 'wb')
        assert cached is None

    def test_empty_rules(self, store):
        rules = store.get_active_rules()
        assert rules == []


class TestLearnedRules:
    def test_save_and_retrieve_rule(self, store):
        rule_id = store.save_learned_rule({
            'rule_type': 'elasticity_override',
            'model': 'wendy',
            'channel': 'wb',
            'content': {'override_elasticity': -0.8},
            'source': 'user_feedback',
            'confidence': 0.9,
        })
        assert rule_id > 0

        rules = store.get_active_rules(model='wendy', channel='wb')
        assert len(rules) >= 1
        assert rules[0]['rule_type'] == 'elasticity_override'


class TestPromotionRecommendation:
    def test_save_promotion(self, store):
        rec_id = store.save_promotion_recommendation({
            'channel': 'wb',
            'promotion_id': '12345',
            'promotion_name': 'Неделя моды',
            'promotion_start': '2026-02-20',
            'promotion_end': '2026-02-27',
            'recommendation': 'participate',
            'predicted_net_impact': 6160.0,
            'models_affected': ['wendy', 'ruby'],
        })
        assert rec_id > 0
