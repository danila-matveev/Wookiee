"""Filter known bots out of participant lists for meeting-ended detection."""
from services.telemost_recorder.join import _filter_human_participants


def test_filter_removes_known_bots_case_insensitive():
    names = ["Данила Матвеев", "Wookiee Recorder", "navstreche.com ИИ-ассистент", "Алина"]
    humans = _filter_human_participants(names)
    assert humans == ["Данила Матвеев", "Алина"]


def test_filter_handles_bot_name_substring():
    names = ["Sber Salut Bot 2.0", "Артём"]
    humans = _filter_human_participants(names)
    assert humans == ["Артём"]


def test_filter_keeps_human_names_with_similar_substrings():
    """Tightened tokens (sber salut, not salut) must not drop legit names."""
    names = ["Salutamica Ivanova", "Salutogenesis Co.", "Александр Хорошев"]
    humans = _filter_human_participants(names)
    assert humans == ["Salutamica Ivanova", "Salutogenesis Co.", "Александр Хорошев"]


def test_filter_empty_list():
    assert _filter_human_participants([]) == []


def test_filter_only_bots_returns_empty():
    names = ["Wookiee Recorder", "navstreche.com"]
    assert _filter_human_participants(names) == []


def test_filter_preserves_order():
    names = ["Артём", "Wookiee Recorder", "Данила", "Sber Salut"]
    assert _filter_human_participants(names) == ["Артём", "Данила"]
