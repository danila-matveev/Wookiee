"""Test q-filter for integrations list."""
from unittest.mock import MagicMock
from shared.data_layer.influencer_crm.integrations import list_integrations


def _make_session(rows):
    session = MagicMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    session.execute.return_value = result
    return session


def test_q_filter_adds_ilike_clause():
    """When q is provided, SQL must filter by blogger handle case-insensitively."""
    session = _make_session([])
    list_integrations(session, q="wendy", limit=10)
    call_args = session.execute.call_args
    sql = str(call_args[0][0])
    assert "LOWER" in sql or "ILIKE" in sql.upper(), (
        "q filter must use case-insensitive search on blogger handle"
    )


def test_q_filter_not_added_when_none():
    """When q is None, SQL must not contain q_pattern binding."""
    session = _make_session([])
    list_integrations(session, limit=10)
    call_args = session.execute.call_args
    # Second arg is the params dict
    if len(call_args[0]) > 1:
        params = call_args[0][1]
    else:
        params = call_args[1].get('params', {})
    assert "q_pattern" not in str(params)
