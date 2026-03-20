"""
Full Finolog transaction analysis — fetch ALL historical transactions,
build pattern statistics, validate existing rules, find gaps.

Outputs JSON data dump + analysis summary.
"""
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

API_BASE = "https://api.finolog.ru/v1"
API_KEY = os.getenv("FINOLOG_API_KEY", "")
BIZ_ID = int(os.getenv("FINOLOG_BIZ_ID", "48556"))
HEADERS = {"Api-Token": API_KEY, "Content-Type": "application/json"}

DATA_DIR = ROOT / "data" / "finolog_analysis"
DATA_DIR.mkdir(parents=True, exist_ok=True)


async def fetch_all(path: str, params: dict = None) -> list[dict]:
    """Fetch all pages from a paginated endpoint."""
    all_items = []
    page = 1
    base_params = params or {}
    async with httpx.AsyncClient(timeout=60, headers=HEADERS) as client:
        while True:
            p = {**base_params, "per_page": 200, "page": page}
            resp = await client.get(f"{API_BASE}{path}", params=p)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            all_items.extend(data)
            print(f"  page {page}: +{len(data)} items (total: {len(all_items)})")
            if len(data) < 200:
                break
            page += 1
    return all_items


async def fetch_transactions_by_year(year: int) -> list[dict]:
    """Fetch all transactions for a given year."""
    print(f"\n=== Fetching year {year} ===")
    return await fetch_all(
        f"/biz/{BIZ_ID}/transaction",
        params={
            "report_date_from": f"{year}-01-01",
            "report_date_to": f"{year}-12-31",
        },
    )


async def main():
    if not API_KEY:
        print("ERROR: FINOLOG_API_KEY not set")
        return

    # 1. Fetch categories and contractors
    print("Fetching categories...")
    categories = await fetch_all(f"/biz/{BIZ_ID}/category")
    cat_map = {c["id"]: c["name"] for c in categories}
    with open(DATA_DIR / "categories.json", "w") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
    print(f"  {len(categories)} categories")

    print("\nFetching contractors...")
    contractors = await fetch_all(f"/biz/{BIZ_ID}/contractor")
    contractor_map = {c["id"]: c.get("name", "") for c in contractors}
    with open(DATA_DIR / "contractors.json", "w") as f:
        json.dump(contractors, f, ensure_ascii=False, indent=2)
    print(f"  {len(contractors)} contractors")

    # 2. Fetch ALL transactions year by year (2022-2026)
    all_txns = []
    for year in range(2022, 2027):
        txns = await fetch_transactions_by_year(year)
        all_txns.extend(txns)

    print(f"\n=== TOTAL: {len(all_txns)} transactions ===")

    # Deduplicate by ID
    seen = set()
    unique_txns = []
    for t in all_txns:
        tid = t.get("id")
        if tid and tid not in seen:
            seen.add(tid)
            unique_txns.append(t)
    print(f"Unique: {len(unique_txns)} (deduped from {len(all_txns)})")

    # Save raw data
    with open(DATA_DIR / "all_transactions.json", "w") as f:
        json.dump(unique_txns, f, ensure_ascii=False, indent=2)
    print(f"Saved to {DATA_DIR / 'all_transactions.json'}")

    # 3. Analysis
    print("\n=== ANALYSIS ===\n")

    # Basic stats
    total = len(unique_txns)
    by_status = Counter(t.get("status", "unknown") for t in unique_txns)
    by_type = Counter(t.get("type", "unknown") for t in unique_txns)
    print(f"Total transactions: {total}")
    print(f"By status: {dict(by_status)}")
    print(f"By type: {dict(by_type)}")

    # Category distribution
    cat_counter = Counter()
    cat_amounts = defaultdict(float)
    for t in unique_txns:
        cid = t.get("category_id")
        cname = cat_map.get(cid, f"#{cid}")
        cat_counter[cname] += 1
        cat_amounts[cname] += abs(t.get("value", 0) or 0)

    print(f"\nCategories used: {len(cat_counter)}")
    print("\nTop 30 categories by frequency:")
    for name, count in cat_counter.most_common(30):
        amt = cat_amounts[name]
        print(f"  {count:5d}x  {amt:>14,.0f} ₽  {name}")

    # Description patterns (first 60 chars, normalized)
    desc_counter = Counter()
    desc_to_cats = defaultdict(Counter)
    for t in unique_txns:
        desc = (t.get("description") or "").strip()
        if not desc:
            continue
        # Normalize: first 60 chars
        key = desc[:60]
        cid = t.get("category_id")
        cname = cat_map.get(cid, f"#{cid}")
        desc_counter[key] += 1
        desc_to_cats[key][cname] += 1

    print(f"\nUnique description prefixes (60 chars): {len(desc_counter)}")
    print("\nTop 50 description patterns:")
    for desc, count in desc_counter.most_common(50):
        cats = desc_to_cats[desc]
        top_cat = cats.most_common(1)[0]
        ambiguous = " ⚠️ AMBIGUOUS" if len(cats) > 1 else ""
        print(f"  {count:5d}x  [{top_cat[0]}]  {desc}{ambiguous}")
        if len(cats) > 1:
            for c, n in cats.most_common():
                print(f"         -> {n}x {c}")

    # Contractor → category mapping
    contr_cat_map = defaultdict(Counter)
    for t in unique_txns:
        ctr_id = t.get("contractor_id")
        if not ctr_id:
            continue
        cid = t.get("category_id")
        cname = cat_map.get(cid, f"#{cid}")
        ctr_name = contractor_map.get(ctr_id, f"#{ctr_id}")
        contr_cat_map[ctr_name][cname] += 1

    print(f"\nContractors with transactions: {len(contr_cat_map)}")
    print("\nContractor → category (top 40 by frequency):")
    sorted_contractors = sorted(contr_cat_map.items(), key=lambda x: sum(x[1].values()), reverse=True)
    for ctr_name, cats in sorted_contractors[:40]:
        total_c = sum(cats.values())
        top_cat = cats.most_common(1)[0]
        ambiguous = " ⚠️" if len(cats) > 1 else ""
        print(f"  {total_c:5d}x  {ctr_name[:40]}  → {top_cat[0]}{ambiguous}")
        if len(cats) > 1:
            for c, n in cats.most_common(3):
                print(f"         -> {n}x {c}")

    # Accrual patterns (report_date != date)
    accrual_count = 0
    accrual_by_cat = defaultdict(int)
    for t in unique_txns:
        d = (t.get("date") or "")[:10]
        rd = (t.get("report_date") or "")[:10]
        if d and rd and d != rd:
            accrual_count += 1
            cid = t.get("category_id")
            cname = cat_map.get(cid, f"#{cid}")
            accrual_by_cat[cname] += 1

    print(f"\nTransactions with accrual (date != report_date): {accrual_count}")
    print("By category:")
    for cname, cnt in sorted(accrual_by_cat.items(), key=lambda x: -x[1])[:20]:
        print(f"  {cnt:5d}x  {cname}")

    # Uncategorized
    uncat = [t for t in unique_txns if t.get("category_id") in (3, 4)]
    print(f"\nUncategorized (cat 3/4): {len(uncat)}")
    for t in uncat[:20]:
        desc = (t.get("description") or "")[:60]
        val = t.get("value", 0)
        d = (t.get("date") or "")[:10]
        print(f"  {d}  {val:>12,.0f} ₽  {desc}")

    # Test current rule engine against ALL historical data
    print("\n=== RULE ENGINE VALIDATION ===\n")

    from agents.oleg.services.finolog_categorizer import classify

    correct = 0
    wrong = 0
    no_match = 0
    wrong_details = []

    for t in unique_txns:
        actual_cat = t.get("category_id")
        if not actual_cat or actual_cat in (1, 3, 4):  # skip transfers and uncategorized
            continue

        suggestion = classify(t)
        if suggestion is None:
            no_match += 1
        elif suggestion.category_id == actual_cat:
            correct += 1
        else:
            wrong += 1
            if len(wrong_details) < 200:
                wrong_details.append({
                    "txn_id": t.get("id"),
                    "description": (t.get("description") or "")[:80],
                    "actual_cat": cat_map.get(actual_cat, f"#{actual_cat}"),
                    "actual_cat_id": actual_cat,
                    "predicted_cat": cat_map.get(suggestion.category_id, f"#{suggestion.category_id}"),
                    "predicted_cat_id": suggestion.category_id,
                    "rule": suggestion.rule_name,
                    "confidence": suggestion.confidence,
                })

    classified = correct + wrong + no_match
    print(f"Classified transactions (excl transfers/uncategorized): {classified}")
    print(f"  ✅ Correct: {correct} ({correct/classified*100:.1f}%)")
    print(f"  ❌ Wrong: {wrong} ({wrong/classified*100:.1f}%)")
    print(f"  ❓ No match: {no_match} ({no_match/classified*100:.1f}%)")

    # Group wrong predictions
    wrong_grouped = defaultdict(list)
    for w in wrong_details:
        key = f"{w['actual_cat']} (predicted: {w['predicted_cat']}, rule: {w['rule']})"
        wrong_grouped[key].append(w)

    print(f"\nWrong predictions grouped ({len(wrong_grouped)} patterns):")
    for key, items in sorted(wrong_grouped.items(), key=lambda x: -len(x[1]))[:30]:
        print(f"  {len(items):4d}x  {key}")
        for item in items[:3]:
            print(f"         {item['description']}")

    # No-match analysis: what categories are we missing?
    no_match_cats = Counter()
    no_match_descs = []
    for t in unique_txns:
        actual_cat = t.get("category_id")
        if not actual_cat or actual_cat in (1, 3, 4):
            continue
        suggestion = classify(t)
        if suggestion is None:
            cname = cat_map.get(actual_cat, f"#{actual_cat}")
            no_match_cats[cname] += 1
            if len(no_match_descs) < 200:
                no_match_descs.append({
                    "description": (t.get("description") or "")[:100],
                    "category": cname,
                    "category_id": actual_cat,
                    "value": t.get("value", 0),
                })

    print(f"\nNo-match by actual category:")
    for cname, cnt in no_match_cats.most_common(20):
        print(f"  {cnt:5d}x  {cname}")

    print(f"\nSample no-match descriptions:")
    for item in no_match_descs[:30]:
        print(f"  [{item['category']}]  {item['description']}")

    # Save analysis results
    analysis = {
        "total_transactions": total,
        "unique_transactions": len(unique_txns),
        "by_status": dict(by_status),
        "by_type": dict(by_type),
        "categories_used": len(cat_counter),
        "rule_validation": {
            "correct": correct,
            "wrong": wrong,
            "no_match": no_match,
            "accuracy": correct / classified * 100 if classified else 0,
        },
        "wrong_predictions": wrong_details,
        "no_match_samples": no_match_descs,
        "top_description_patterns": [
            {
                "pattern": desc,
                "count": count,
                "categories": dict(desc_to_cats[desc]),
            }
            for desc, count in desc_counter.most_common(100)
        ],
        "contractor_category_map": {
            name: dict(cats)
            for name, cats in sorted_contractors[:50]
        },
        "accrual_by_category": dict(accrual_by_cat),
    }

    with open(DATA_DIR / "analysis_results.json", "w") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    print(f"\nAnalysis saved to {DATA_DIR / 'analysis_results.json'}")
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
