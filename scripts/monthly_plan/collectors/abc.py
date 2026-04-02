"""ABC classification collector."""
from shared.data_layer.planning import get_active_models_with_abc


def collect_abc(current_start: str, current_end: str) -> dict:
    """Collect ABC classification data.

    Returns dict with abc classification list and summary.
    """
    abc_data = get_active_models_with_abc(current_start, current_end)

    # abc_data is list of dicts:
    # [{model, total_margin, articles: [{artikul, abc_class, margin, margin_share_pct, orders, opens}]}]

    classification = []
    for model_data in abc_data:
        a_count = sum(1 for a in model_data["articles"] if a["abc_class"] == "A")
        b_count = sum(1 for a in model_data["articles"] if a["abc_class"] == "B")
        c_count = sum(1 for a in model_data["articles"] if a["abc_class"] == "C")

        classification.append({
            "model": model_data["model"],
            "total_margin": model_data["total_margin"],
            "article_count": len(model_data["articles"]),
            "a_count": a_count,
            "b_count": b_count,
            "c_count": c_count,
            "articles": model_data["articles"],
        })

    return {"abc": {"classification": classification}}
