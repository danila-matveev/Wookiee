"""Sheets ETL configuration: spreadsheet ID + load order."""
from __future__ import annotations

SPREADSHEET_ID = "1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk"

# Order matters: dictionaries first (promo codes, bloggers, substitute articles),
# then dependents (integrations link to bloggers; candidates pipeline last).
LOAD_ORDER = [
    "Промокоды_справочник",
    "БД БЛОГЕРЫ",
    "Подменные",
    "Блогеры",
    "inst на проверку",
]
