"""Sync Google Sheets → Supabase (product matrix).

Usage:
    python scripts/sync_sheets_to_supabase.py [--level LEVEL] [--dry-run] [--spreadsheet-id ID]

Levels: all (default), statusy, modeli_osnova, modeli, artikuly, tovary
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import gspread
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Constants ---

SPREADSHEET_ID = os.getenv(
    "PRODUCT_MATRIX_SPREADSHEET_ID",
    "19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg",
)

LEVELS_ORDER = ["statusy", "cveta", "modeli_osnova", "modeli", "artikuly", "tovary", "skleyki_ozon"]

SA_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "services/sheets_sync/credentials/google_sa.json",
)

ARCHIVE_STATUS = "Архив"


# --- Supabase connection ---

def get_supabase_conn():
    """Connect to Supabase via psycopg2."""
    return psycopg2.connect(
        host=os.getenv("SUPABASE_HOST", "aws-1-ap-northeast-2.pooler.supabase.com"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER", "postgres"),
        password=os.getenv("SUPABASE_PASSWORD", ""),
    )


def query_all(conn, sql: str) -> list[dict]:
    """Execute SQL and return list of dicts."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        return [dict(row) for row in cur.fetchall()]


# --- Sheets loader ---

def get_sheets_client() -> gspread.Client:
    """Authenticate and return gspread client."""
    creds = Credentials.from_service_account_file(
        SA_FILE,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    return gspread.authorize(creds)


def load_sheet_as_dicts(client: gspread.Client, spreadsheet_id: str, tab_name: str) -> list[dict]:
    """Load a sheet tab as list of dicts (header row = keys)."""
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(tab_name)
    rows = ws.get_all_values()
    if len(rows) < 2:
        return []
    headers = rows[0]
    result = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        d = {}
        for i, h in enumerate(headers):
            if h and i < len(row):
                d[h] = row[i]
        result.append(d)
    return result


# --- Normalization ---

def normalize_key(value: str) -> str:
    """Normalize a text key: lowercase, strip, remove trailing /."""
    if not value:
        return ""
    return value.strip().lower().rstrip("/")


def clean_barcode(value: str) -> Optional[str]:
    """Clean barcode value; return None if invalid."""
    if not value or not value.strip():
        return None
    v = value.strip()
    if v.endswith(".0"):
        v = v[:-2]
    if not v.isdigit() or len(v) < 10:
        return None
    return v


def clean_string(value: str) -> Optional[str]:
    """Clean string value."""
    if not value or not value.strip() or value.strip().lower() == "nan":
        return None
    return value.strip()


def clean_numeric(value: str) -> Optional[float]:
    """Clean numeric value."""
    if not value or not value.strip():
        return None
    try:
        return float(value.replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except (ValueError, TypeError):
        return None


def clean_integer(value: str) -> Optional[int]:
    """Clean integer value."""
    n = clean_numeric(value)
    return int(n) if n is not None else None


def clean_boolean(value: str) -> bool:
    """Convert to boolean."""
    if not value:
        return False
    return value.strip().lower() in ("да", "yes", "true", "1", "д")


# --- Diff Engine ---

def compute_diff(
    sheets_records: list[dict],
    supabase_records: list[dict],
    key_field: str,
    compare_fields: list[str],
) -> dict:
    """Compare Sheets vs Supabase records.

    Returns dict with keys: to_insert, to_update, to_soft_delete, unchanged.
    """
    sheets_by_key = {}
    for r in sheets_records:
        k = normalize_key(str(r.get(key_field, "")))
        if k:
            sheets_by_key[k] = r

    supa_by_key = {}
    for r in supabase_records:
        k = normalize_key(str(r.get(key_field, "")))
        if k:
            supa_by_key[k] = r

    to_insert = []
    to_update = []
    unchanged = 0

    for k, sheets_rec in sheets_by_key.items():
        if k not in supa_by_key:
            to_insert.append(sheets_rec)
        else:
            supa_rec = supa_by_key[k]
            changed_fields = {}
            for field in compare_fields:
                sv = str(sheets_rec.get(field, "") or "").strip()
                dv = str(supa_rec.get(field, "") or "").strip()
                if sv != dv:
                    changed_fields[field] = {"old": dv, "new": sv}
            if changed_fields:
                to_update.append({
                    "sheets": sheets_rec,
                    "supabase": supa_rec,
                    "changed_fields": changed_fields,
                })
            else:
                unchanged += 1

    to_soft_delete = [
        supa_by_key[k] for k in supa_by_key if k not in sheets_by_key
    ]

    return {
        "to_insert": to_insert,
        "to_update": to_update,
        "to_soft_delete": to_soft_delete,
        "unchanged": unchanged,
    }


# --- Reference table helpers ---

def ensure_reference(conn, table: str, name_field: str, value: str) -> Optional[int]:
    """Get or create a reference record, return its id."""
    if not value or not value.strip():
        return None
    value = value.strip()
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id FROM {table} WHERE {name_field} = %s",
            (value,),
        )
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            f"INSERT INTO {table} ({name_field}) VALUES (%s) RETURNING id",
            (value,),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"  Created {table}: {value} (id={new_id})")
        return new_id


def get_status_id(conn, status_name: str) -> Optional[int]:
    """Get status id, applying legacy mapping if needed."""
    if not status_name or not status_name.strip():
        return None
    # Legacy status mapping from mapping.py
    MODEL_STATUS_MAP = {
        "В продаже": "Продается",
        "Планирование": "План",
        "Закуп": "Подготовка",
        "В разработке": "Подготовка",
        "Делаем образец": "Новый",
    }
    mapped = MODEL_STATUS_MAP.get(status_name.strip(), status_name.strip())
    return ensure_reference(conn, "statusy", "nazvanie", mapped)


def get_archive_status_id(conn) -> int:
    """Get or create 'Архив' status id."""
    sid = ensure_reference(conn, "statusy", "nazvanie", ARCHIVE_STATUS)
    assert sid is not None, "Failed to get/create 'Архив' status"
    return sid


def sync_cveta(conn, sheets_tovary: list[dict], log: dict, dry_run: bool) -> dict:
    """Sync cveta table from Все товары color codes.

    Returns mapping: normalize_key(color_code) → cvet_id.
    """
    # Collect unique color codes from Sheets
    seen = {}
    for row in sheets_tovary:
        cc = clean_string(row.get("Color code", ""))
        color_name = clean_string(row.get("Сolor", "")) or clean_string(row.get("Цвет", ""))
        color_en = clean_string(row.get("Сolor", ""))
        if cc:
            key = normalize_key(cc)
            if key not in seen:
                seen[key] = {"color_code": cc, "cvet": color_name, "color": color_en}

    # Load existing cveta
    existing = query_all(conn, "SELECT id, color_code, cvet, color FROM cveta")
    existing_by_key = {normalize_key(r["color_code"]): r for r in existing}

    inserted = 0
    updated = 0
    cvet_map = {}

    for key, data in seen.items():
        if key in existing_by_key:
            cvet_map[key] = existing_by_key[key]["id"]
            # Check if cvet/color changed
            ex = existing_by_key[key]
            changes = {}
            if data["cvet"] and data["cvet"] != (ex.get("cvet") or ""):
                changes["cvet"] = data["cvet"]
            if data["color"] and data["color"] != (ex.get("color") or ""):
                changes["color"] = data["color"]
            if changes and not dry_run:
                sets = ", ".join(f"{k} = %s" for k in changes)
                vals = list(changes.values()) + [ex["id"]]
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE cveta SET {sets}, updated_at = NOW() WHERE id = %s", vals)
                conn.commit()
                updated += 1
                log["details"].append({
                    "action": "update", "level": "cveta",
                    "key": data["color_code"], "changed_fields": changes,
                })
        else:
            if not dry_run:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO cveta (color_code, cvet, color) VALUES (%s, %s, %s) RETURNING id",
                        (data["color_code"], data["cvet"], data["color"]),
                    )
                    cvet_map[key] = cur.fetchone()[0]
                conn.commit()
            inserted += 1
            log["details"].append({
                "action": "insert", "level": "cveta",
                "key": data["color_code"],
            })

    # Map existing keys too
    for key, ex in existing_by_key.items():
        if key not in cvet_map:
            cvet_map[key] = ex["id"]

    log["summary"]["cveta"] = {
        "inserted": inserted, "updated": updated,
        "soft_deleted": 0, "unchanged": len(existing) - updated,
    }
    logger.info(f"cveta: {inserted} new, {updated} updated")
    return cvet_map


def sync_modeli_osnova(conn, sheets_modeli: list[dict], log: dict, dry_run: bool) -> dict:
    """Sync modeli_osnova from 'Все модели' tab.

    Returns mapping: normalize_key(kod) → id.
    """
    # Parse sheets records — deduplicate by "Модель основа" (col H)
    # "Модель основа" = Vuki, Moon, Ruby (modeli_osnova.kod)
    # "Артикул модели" = компбел-ж-бесшов/ (modeli.artikul_modeli, NOT osnova key)
    seen_keys = set()
    sheets_records = []
    for row in sheets_modeli:
        kod = clean_string(row.get("Модель основа", ""))
        if not kod:
            continue
        key = normalize_key(kod)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        sheets_records.append({
            "kod": key,
            "kod_raw": kod.strip(),
            "kategoriya": clean_string(row.get("Категория", "")),
            "kollekciya": clean_string(row.get("Коллекция", "")),
            "fabrika": clean_string(row.get("Фабрика", "")),
            "nazvanie_etiketka": clean_string(row.get("Название для Этикетки", "")),
            "nazvanie_sayt": clean_string(row.get("Название для сайта", "")),
            "opisanie_sayt": clean_string(row.get("Описание для сайта", "")),
            "details": clean_string(row.get("Details", "")),
            "tegi": clean_string(row.get("Теги", "")),
            "material": clean_string(row.get("Материал", "")),
            "sostav_syrya": clean_string(row.get("Состав сырья", "")),
            "sku_china": clean_string(row.get("SKU CHINA", "")),
            "upakovka": clean_string(row.get("Упаковка", "")),
            "ves_kg": clean_numeric(row.get("Вес (кг)", "")),
            "razmery_modeli": clean_string(row.get("Размеры модели", "")),
            "dlya_kakoy_grudi": clean_string(row.get("Для какой груди", "")),
            "stepen_podderzhki": clean_string(row.get("Степень поддержки груди/в характеристике карточки", "")),
            "forma_chashki": clean_string(row.get("Форма чашки", "")),
            "regulirovka": clean_string(row.get("Регулировка", "")),
            "zastezhka": clean_string(row.get("Застежка", "")),
            "posadka_trusov": clean_string(row.get("Посадка трусов", "")),
            "vid_trusov": clean_string(row.get("Вид трусов", "")),
            "naznachenie": clean_string(row.get("Назначение", "")),
            "stil": clean_string(row.get("Стиль", "")),
            "po_nastroeniyu": clean_string(row.get("По настроению", "")),
            "tnved": clean_string(row.get("ТНВЭД", "")),
        })

    # Load existing
    existing = query_all(conn, "SELECT * FROM modeli_osnova")
    existing_by_key = {normalize_key(r["kod"]): r for r in existing}

    inserted, updated = 0, 0
    osnova_map = {}

    COMPARE_FIELDS = [
        "nazvanie_etiketka", "nazvanie_sayt", "opisanie_sayt", "details",
        "tegi", "material", "sostav_syrya", "sku_china", "upakovka",
        "razmery_modeli", "dlya_kakoy_grudi", "stepen_podderzhki",
        "forma_chashki", "regulirovka", "zastezhka", "posadka_trusov",
        "vid_trusov", "naznachenie", "stil", "po_nastroeniyu", "tnved",
    ]

    for rec in sheets_records:
        key = rec["kod"]
        if key in existing_by_key:
            ex = existing_by_key[key]
            osnova_map[key] = ex["id"]
            # Check for field changes
            changes = {}
            for f in COMPARE_FIELDS:
                new_val = rec.get(f)
                old_val = ex.get(f)
                new_s = str(new_val or "").strip()
                old_s = str(old_val or "").strip()
                if new_s and new_s != old_s:
                    changes[f] = new_val
            # Update FK references
            if rec["kategoriya"]:
                kat_id = ensure_reference(conn, "kategorii", "nazvanie", rec["kategoriya"])
                if kat_id != ex.get("kategoriya_id"):
                    changes["kategoriya_id"] = kat_id
            if rec["kollekciya"]:
                kol_id = ensure_reference(conn, "kollekcii", "nazvanie", rec["kollekciya"])
                if kol_id != ex.get("kollekciya_id"):
                    changes["kollekciya_id"] = kol_id
            if rec["fabrika"]:
                fab_id = ensure_reference(conn, "fabriki", "nazvanie", rec["fabrika"])
                if fab_id != ex.get("fabrika_id"):
                    changes["fabrika_id"] = fab_id

            if changes and not dry_run:
                sets = ", ".join(f"{k} = %s" for k in changes)
                vals = list(changes.values()) + [ex["id"]]
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE modeli_osnova SET {sets}, updated_at = NOW() WHERE id = %s", vals)
                conn.commit()
                updated += 1
                log["details"].append({
                    "action": "update", "level": "modeli_osnova",
                    "key": rec["kod_raw"], "changed_fields": {k: str(v) for k, v in changes.items()},
                })
        else:
            if not dry_run:
                kat_id = ensure_reference(conn, "kategorii", "nazvanie", rec["kategoriya"]) if rec["kategoriya"] else None
                kol_id = ensure_reference(conn, "kollekcii", "nazvanie", rec["kollekciya"]) if rec["kollekciya"] else None
                fab_id = ensure_reference(conn, "fabriki", "nazvanie", rec["fabrika"]) if rec["fabrika"] else None
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO modeli_osnova (kod, kategoriya_id, kollekciya_id, fabrika_id,
                           nazvanie_etiketka, nazvanie_sayt, opisanie_sayt, details, tegi,
                           material, sostav_syrya, sku_china, upakovka, ves_kg, razmery_modeli,
                           dlya_kakoy_grudi, stepen_podderzhki, forma_chashki, regulirovka,
                           zastezhka, posadka_trusov, vid_trusov, naznachenie, stil, po_nastroeniyu, tnved)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           RETURNING id""",
                        (rec["kod_raw"], kat_id, kol_id, fab_id,
                         rec["nazvanie_etiketka"], rec["nazvanie_sayt"], rec["opisanie_sayt"],
                         rec["details"], rec["tegi"], rec["material"], rec["sostav_syrya"],
                         rec["sku_china"], rec["upakovka"], rec["ves_kg"], rec["razmery_modeli"],
                         rec["dlya_kakoy_grudi"], rec["stepen_podderzhki"], rec["forma_chashki"],
                         rec["regulirovka"], rec["zastezhka"], rec["posadka_trusov"],
                         rec["vid_trusov"], rec["naznachenie"], rec["stil"], rec["po_nastroeniyu"],
                         rec["tnved"]),
                    )
                    osnova_map[key] = cur.fetchone()[0]
                conn.commit()
            inserted += 1
            log["details"].append({
                "action": "insert", "level": "modeli_osnova", "key": rec["kod_raw"],
            })

    # Soft-delete check (WARNING only, no action)
    sheets_keys = {r["kod"] for r in sheets_records}
    for key, ex in existing_by_key.items():
        if key not in sheets_keys:
            osnova_map[key] = ex["id"]
            log["warnings"].append(
                f"modeli_osnova '{ex['kod']}' (id={ex['id']}) exists in Supabase but not in Sheets — not deleted (manual review)"
            )

    # Map remaining existing keys
    for key, ex in existing_by_key.items():
        if key not in osnova_map:
            osnova_map[key] = ex["id"]

    log["summary"]["modeli_osnova"] = {
        "inserted": inserted, "updated": updated,
        "soft_deleted": 0, "unchanged": len(existing) - updated,
    }
    logger.info(f"modeli_osnova: {inserted} new, {updated} updated")
    return osnova_map


def sync_modeli(
    conn,
    sheets_modeli: list[dict],
    sheets_tovary: list[dict],
    osnova_map: dict,
    log: dict,
    dry_run: bool,
) -> dict:
    """Sync modeli table.

    Models come from 'Все модели' tab (one row per model).
    Additional model codes come from 'Все товары' col F (Модель).

    Returns mapping: normalize_key(kod) → id.
    """
    # Build model records from 'Все модели'
    # Col A "Модель" = short code (VukiN, MoonW) → used as modeli.kod identifier
    # Col C "Название модели" = display name (Vuki animal, Moon выстиранки) → stored as nazvanie
    # modeli.artikul_modeli = "Артикул модели" (компбел-ж-бесшов/, Vuki/...)
    model_data = {}
    for row in sheets_modeli:
        model_col_a = clean_string(row.get("Модель", ""))
        nazvanie = clean_string(row.get("Название модели", ""))
        # Use col A as the identifier; fall back to col C if col A is empty
        kod_raw = model_col_a if model_col_a else nazvanie
        if not kod_raw:
            continue
        kod = normalize_key(kod_raw)
        if kod in model_data:
            continue
        artikul_modeli = clean_string(row.get("Артикул модели", ""))
        osnova_raw = clean_string(row.get("Модель основа", ""))
        osnova_key = normalize_key(osnova_raw) if osnova_raw else None
        model_data[kod] = {
            "kod_raw": kod_raw.strip(),
            "nazvanie": nazvanie if nazvanie else kod_raw,
            "artikul_modeli": artikul_modeli.strip().rstrip("/") if artikul_modeli else None,
            "model_osnova_key": osnova_key,
            "status": clean_string(row.get("Статус", "")),
            "importer": clean_string(row.get("Импортер", "")),
            "nabor": clean_boolean(row.get("Набор", "")),
            "rossiyskiy_razmer": clean_string(row.get("Российский размер", "")),
        }

    # Collect additional model codes from Все товары that may not be in Все модели
    for row in sheets_tovary:
        model_name = clean_string(row.get("Модель", ""))
        if not model_name:
            continue
        key = normalize_key(model_name)
        if key and key not in model_data:
            osnova_raw = clean_string(row.get("Модель основа", ""))
            model_data[key] = {
                "kod_raw": model_name.strip(),
                "nazvanie": model_name.strip(),
                "model_osnova_key": normalize_key(osnova_raw) if osnova_raw else None,
                "status": clean_string(row.get("Статус товара", "")),
                "importer": clean_string(row.get("Импортер", "")),
                "nabor": False,
                "rossiyskiy_razmer": None,
            }

    # Load existing modeli
    existing = query_all(conn, """
        SELECT m.*, s.nazvanie as status_name, i.nazvanie as importer_name
        FROM modeli m
        LEFT JOIN statusy s ON m.status_id = s.id
        LEFT JOIN importery i ON m.importer_id = i.id
    """)
    existing_by_key = {normalize_key(r["kod"]): r for r in existing}

    inserted, updated, soft_deleted = 0, 0, 0
    model_map = {}
    archive_id = get_archive_status_id(conn)

    for key, data in model_data.items():
        osnova_id = osnova_map.get(data["model_osnova_key"]) if data["model_osnova_key"] else None

        if key in existing_by_key:
            ex = existing_by_key[key]
            model_map[key] = ex["id"]
            changes = {}
            if data["nazvanie"] and data["nazvanie"] != (ex.get("nazvanie") or ""):
                changes["nazvanie"] = data["nazvanie"]
            if osnova_id and osnova_id != ex.get("model_osnova_id"):
                changes["model_osnova_id"] = osnova_id
            if data["status"]:
                new_status_id = get_status_id(conn, data["status"])
                if new_status_id and new_status_id != ex.get("status_id"):
                    changes["status_id"] = new_status_id
            if data["importer"]:
                imp_id = ensure_reference(conn, "importery", "nazvanie", data["importer"])
                if imp_id and imp_id != ex.get("importer_id"):
                    changes["importer_id"] = imp_id

            if changes and not dry_run:
                sets = ", ".join(f"{k} = %s" for k in changes)
                vals = list(changes.values()) + [ex["id"]]
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE modeli SET {sets}, updated_at = NOW() WHERE id = %s", vals)
                conn.commit()
                updated += 1
                log["details"].append({
                    "action": "update", "level": "modeli",
                    "key": data["kod_raw"], "changed_fields": {k: str(v) for k, v in changes.items()},
                })
        else:
            if not dry_run:
                status_id = get_status_id(conn, data["status"])
                imp_id = ensure_reference(conn, "importery", "nazvanie", data["importer"]) if data["importer"] else None
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO modeli (kod, nazvanie, artikul_modeli, model_osnova_id, importer_id, status_id, nabor, rossiyskiy_razmer)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                        (data["kod_raw"][:50], data["nazvanie"][:100],
                         (data.get("artikul_modeli") or "")[:100] or None,
                         osnova_id, imp_id, status_id,
                         data["nabor"], (data["rossiyskiy_razmer"] or "")[:50] or None),
                    )
                    model_map[key] = cur.fetchone()[0]
                conn.commit()
            inserted += 1
            log["details"].append({
                "action": "insert", "level": "modeli", "key": data["kod_raw"],
            })

    # Soft-delete: models in Supabase but not in Sheets → archive
    sheets_keys = set(model_data.keys())
    for key, ex in existing_by_key.items():
        if key not in sheets_keys:
            model_map[key] = ex["id"]
            if ex.get("status_id") != archive_id:
                if not dry_run:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE modeli SET status_id = %s, updated_at = NOW() WHERE id = %s",
                                    (archive_id, ex["id"]))
                    conn.commit()
                soft_deleted += 1
                log["details"].append({
                    "action": "soft_delete", "level": "modeli",
                    "key": ex["kod"], "reason": "not_in_sheets",
                })

    # Map remaining
    for key, ex in existing_by_key.items():
        if key not in model_map:
            model_map[key] = ex["id"]

    log["summary"]["modeli"] = {
        "inserted": inserted, "updated": updated,
        "soft_deleted": soft_deleted, "unchanged": len(existing) - updated - soft_deleted,
    }
    logger.info(f"modeli: {inserted} new, {updated} updated, {soft_deleted} archived")
    return model_map


def sync_artikuly(
    conn,
    sheets_tovary: list[dict],
    model_map: dict,
    cvet_map: dict,
    log: dict,
    dry_run: bool,
) -> dict:
    """Sync artikuly table from 'Все товары'.

    Artikul = unique combination of model + color.

    Returns mapping: normalize_key(artikul) → id.
    """
    # Collect unique artikuly from Sheets
    art_data = {}
    for row in sheets_tovary:
        artikul = clean_string(row.get("Артикул", ""))
        if not artikul:
            continue
        key = normalize_key(artikul)
        if key in art_data:
            continue
        model_name = clean_string(row.get("Модель", ""))
        color_code = clean_string(row.get("Color code", ""))
        status = clean_string(row.get("Статус товара", ""))
        nm_wb = clean_string(row.get("Нуменклатура", "")) or clean_string(row.get("Номенклатура", ""))
        artikul_ozon = clean_string(row.get("Артикул Ozon", ""))

        art_data[key] = {
            "artikul_raw": artikul.strip(),
            "model_key": normalize_key(model_name) if model_name else None,
            "cvet_key": normalize_key(color_code) if color_code else None,
            "status": status,
            "nomenklatura_wb": clean_integer(nm_wb) if nm_wb else None,
            "artikul_ozon": artikul_ozon,
        }

    # Load existing
    existing = query_all(conn, """
        SELECT a.*, s.nazvanie as status_name
        FROM artikuly a LEFT JOIN statusy s ON a.status_id = s.id
    """)
    existing_by_key = {normalize_key(r["artikul"]): r for r in existing}

    inserted, updated, soft_deleted = 0, 0, 0
    art_map = {}
    archive_id = get_archive_status_id(conn)

    for key, data in art_data.items():
        model_id = model_map.get(data["model_key"])
        cvet_id = cvet_map.get(data["cvet_key"])

        if key in existing_by_key:
            ex = existing_by_key[key]
            art_map[key] = ex["id"]
            changes = {}
            if model_id and model_id != ex.get("model_id"):
                changes["model_id"] = model_id
            if cvet_id and cvet_id != ex.get("cvet_id"):
                changes["cvet_id"] = cvet_id
            if data["status"]:
                new_sid = get_status_id(conn, data["status"])
                if new_sid and new_sid != ex.get("status_id"):
                    changes["status_id"] = new_sid
            if data["nomenklatura_wb"] and data["nomenklatura_wb"] != ex.get("nomenklatura_wb"):
                changes["nomenklatura_wb"] = data["nomenklatura_wb"]
            if data["artikul_ozon"] and data["artikul_ozon"] != (ex.get("artikul_ozon") or ""):
                changes["artikul_ozon"] = data["artikul_ozon"]

            if changes and not dry_run:
                sets = ", ".join(f"{k} = %s" for k in changes)
                vals = list(changes.values()) + [ex["id"]]
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE artikuly SET {sets}, updated_at = NOW() WHERE id = %s", vals)
                conn.commit()
                updated += 1
                log["details"].append({
                    "action": "update", "level": "artikuly",
                    "key": data["artikul_raw"], "changed_fields": {k: str(v) for k, v in changes.items()},
                })
        else:
            if not dry_run:
                status_id = get_status_id(conn, data["status"])
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO artikuly (artikul, model_id, cvet_id, status_id, nomenklatura_wb, artikul_ozon)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (artikul) DO UPDATE SET
                               model_id = COALESCE(EXCLUDED.model_id, artikuly.model_id),
                               cvet_id = COALESCE(EXCLUDED.cvet_id, artikuly.cvet_id),
                               status_id = COALESCE(EXCLUDED.status_id, artikuly.status_id),
                               nomenklatura_wb = COALESCE(EXCLUDED.nomenklatura_wb, artikuly.nomenklatura_wb),
                               artikul_ozon = COALESCE(EXCLUDED.artikul_ozon, artikuly.artikul_ozon),
                               updated_at = NOW()
                           RETURNING id""",
                        (data["artikul_raw"], model_id, cvet_id, status_id,
                         data["nomenklatura_wb"], data["artikul_ozon"]),
                    )
                    art_map[key] = cur.fetchone()[0]
                conn.commit()
            inserted += 1
            log["details"].append({
                "action": "insert", "level": "artikuly", "key": data["artikul_raw"],
            })

    # Soft-delete
    sheets_keys = set(art_data.keys())
    for key, ex in existing_by_key.items():
        if key not in sheets_keys:
            art_map[key] = ex["id"]
            if ex.get("status_id") != archive_id:
                if not dry_run:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE artikuly SET status_id = %s, updated_at = NOW() WHERE id = %s",
                                    (archive_id, ex["id"]))
                    conn.commit()
                soft_deleted += 1
                log["details"].append({
                    "action": "soft_delete", "level": "artikuly",
                    "key": ex["artikul"], "reason": "not_in_sheets",
                })

    for key, ex in existing_by_key.items():
        if key not in art_map:
            art_map[key] = ex["id"]

    log["summary"]["artikuly"] = {
        "inserted": inserted, "updated": updated,
        "soft_deleted": soft_deleted, "unchanged": len(existing) - updated - soft_deleted,
    }
    logger.info(f"artikuly: {inserted} new, {updated} updated, {soft_deleted} archived")
    return art_map


def sync_tovary(
    conn,
    sheets_tovary: list[dict],
    art_map: dict,
    log: dict,
    dry_run: bool,
) -> None:
    """Sync tovary table from 'Все товары'."""
    # Parse sheets records
    tovar_data = {}
    for row in sheets_tovary:
        barkod = clean_barcode(row.get("БАРКОД", "") or row.get("БАРКОД ", ""))
        if not barkod:
            continue
        if barkod in tovar_data:
            continue

        artikul = clean_string(row.get("Артикул", ""))
        art_key = normalize_key(artikul) if artikul else None
        razmer = clean_string(row.get("Размер", ""))
        status = clean_string(row.get("Статус товара", ""))
        status_ozon = clean_string(row.get("Статус товара OZON", ""))

        tovar_data[barkod] = {
            "barkod": barkod,
            "barkod_gs1": clean_barcode(row.get("БАРКОД GS1", "")),
            "barkod_gs2": clean_barcode(row.get("БАРКОД GS2", "")),
            "barkod_perehod": clean_barcode(row.get("БАРКОД ПЕРЕХОД", "")),
            "art_key": art_key,
            "razmer": razmer,
            "status": status,
            "status_ozon": status_ozon,
            "ozon_product_id": clean_integer(row.get("Ozon Product ID", "")),
            "ozon_fbo_sku_id": clean_integer(row.get("FBO OZON SKU ID", "")),
            "lamoda_seller_sku": clean_string(row.get("Seller SKU Lamoda", "")),
            "sku_china_size": clean_string(row.get("SKU CHINA SIZE", "")),
        }

    # Load existing
    existing = query_all(conn, "SELECT * FROM tovary")
    existing_by_barkod = {r["barkod"]: r for r in existing if r["barkod"]}

    inserted, updated, soft_deleted = 0, 0, 0
    archive_id = get_archive_status_id(conn)

    # Pre-cache razmery and statusy to avoid N+1 queries
    razmer_cache = {}
    for r in query_all(conn, "SELECT id, nazvanie FROM razmery"):
        razmer_cache[r["nazvanie"]] = r["id"]
    status_cache = {}
    for r in query_all(conn, "SELECT id, nazvanie FROM statusy"):
        status_cache[r["nazvanie"]] = r["id"]

    MODEL_STATUS_MAP = {
        "В продаже": "Продается",
        "Планирование": "План",
        "Закуп": "Подготовка",
        "В разработке": "Подготовка",
        "Делаем образец": "Новый",
    }

    def _get_razmer_id(name):
        if not name:
            return None
        if name in razmer_cache:
            return razmer_cache[name]
        rid = ensure_reference(conn, "razmery", "nazvanie", name)
        razmer_cache[name] = rid
        return rid

    def _get_status_id_cached(name):
        if not name or not name.strip():
            return None
        mapped = MODEL_STATUS_MAP.get(name.strip(), name.strip())
        if mapped in status_cache:
            return status_cache[mapped]
        sid = ensure_reference(conn, "statusy", "nazvanie", mapped)
        status_cache[mapped] = sid
        return sid

    for barkod, data in tovar_data.items():
        artikul_id = art_map.get(data["art_key"])
        razmer_id = _get_razmer_id(data["razmer"])
        status_id = _get_status_id_cached(data["status"])
        status_ozon_id = _get_status_id_cached(data["status_ozon"])

        if barkod in existing_by_barkod:
            ex = existing_by_barkod[barkod]
            changes = {}
            if artikul_id and artikul_id != ex.get("artikul_id"):
                changes["artikul_id"] = artikul_id
            if razmer_id and razmer_id != ex.get("razmer_id"):
                changes["razmer_id"] = razmer_id
            if status_id and status_id != ex.get("status_id"):
                changes["status_id"] = status_id
            if status_ozon_id and status_ozon_id != ex.get("status_ozon_id"):
                changes["status_ozon_id"] = status_ozon_id
            if data["barkod_gs1"] and data["barkod_gs1"] != (ex.get("barkod_gs1") or ""):
                changes["barkod_gs1"] = data["barkod_gs1"]
            if data["barkod_gs2"] and data["barkod_gs2"] != (ex.get("barkod_gs2") or ""):
                changes["barkod_gs2"] = data["barkod_gs2"]
            if data["ozon_product_id"] and data["ozon_product_id"] != ex.get("ozon_product_id"):
                changes["ozon_product_id"] = data["ozon_product_id"]
            if data["ozon_fbo_sku_id"] and data["ozon_fbo_sku_id"] != ex.get("ozon_fbo_sku_id"):
                changes["ozon_fbo_sku_id"] = data["ozon_fbo_sku_id"]

            if changes and not dry_run:
                sets = ", ".join(f"{k} = %s" for k in changes)
                vals = list(changes.values()) + [ex["id"]]
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE tovary SET {sets}, updated_at = NOW() WHERE id = %s", vals)
                conn.commit()
                updated += 1
                log["details"].append({
                    "action": "update", "level": "tovary",
                    "key": barkod,
                    "changed_fields": {k: str(v) for k, v in changes.items()},
                })
        else:
            if not dry_run:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO tovary (barkod, barkod_gs1, barkod_gs2, barkod_perehod,
                           artikul_id, razmer_id, status_id, status_ozon_id,
                           ozon_product_id, ozon_fbo_sku_id, lamoda_seller_sku, sku_china_size)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (barkod, data["barkod_gs1"], data["barkod_gs2"], data["barkod_perehod"],
                         artikul_id, razmer_id, status_id, status_ozon_id,
                         data["ozon_product_id"], data["ozon_fbo_sku_id"],
                         data["lamoda_seller_sku"], data["sku_china_size"]),
                    )
                conn.commit()
            inserted += 1
            log["details"].append({
                "action": "insert", "level": "tovary", "key": barkod,
            })

    # Soft-delete
    sheets_barcodes = set(tovar_data.keys())
    for barkod, ex in existing_by_barkod.items():
        if barkod not in sheets_barcodes and ex.get("status_id") != archive_id:
            if not dry_run:
                with conn.cursor() as cur:
                    cur.execute("UPDATE tovary SET status_id = %s, updated_at = NOW() WHERE id = %s",
                                (archive_id, ex["id"]))
                conn.commit()
            soft_deleted += 1
            if soft_deleted <= 50:
                log["details"].append({
                    "action": "soft_delete", "level": "tovary",
                    "key": barkod, "reason": "not_in_sheets",
                })

    log["summary"]["tovary"] = {
        "inserted": inserted, "updated": updated,
        "soft_deleted": soft_deleted, "unchanged": len(existing) - updated - soft_deleted,
    }
    logger.info(f"tovary: {inserted} new, {updated} updated, {soft_deleted} archived")


# --- Склейки Озон ---

def load_sheet_as_rows(client: gspread.Client, spreadsheet_id: str, tab_name: str) -> list[list[str]]:
    """Load a sheet tab as raw list of rows (list of lists), skipping fully-empty rows."""
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(tab_name)
    rows = ws.get_all_values()
    return [row for row in rows if any(cell.strip() for cell in row)]


def sync_skleyki_ozon(
    conn,
    raw_rows: list[list[str]],
    importer_map: dict[str, int],
    log: dict,
    dry_run: bool,
) -> None:
    """Sync skleyki_ozon and tovary_skleyki_ozon from 'Склейки Озон' sheet.

    Sheet layout (0-indexed columns):
      col 0 – importer ("ИП" / "ООО")
      col 1 – skleyka name (e.g. "ООО_склейка_Joy")
      col 3 – artikul_ozon (e.g. "Joy/white_S")
      col 4 – SKU ozon
      col 5 – model name

    Row 0 is a header-like row and is skipped (col 0 is empty there).
    """
    # Skip row 0 (header) and rows where col 1 is empty
    data_rows = []
    for row in raw_rows:
        # Pad row to at least 6 columns
        padded = row + [""] * max(0, 6 - len(row))
        col0 = padded[0].strip()
        col1 = padded[1].strip()
        if not col1 or col1 == "Склейкообразующий признак":
            continue
        data_rows.append(padded)

    if not data_rows:
        logger.warning("sync_skleyki_ozon: no data rows found in sheet")
        log["summary"]["skleyki_ozon"] = {"inserted_skleyki": 0, "inserted_tovary": 0, "skipped": 0}
        return

    # Build unique skleyki: name → importer key
    skleyki_names: dict[str, str] = {}
    for row in data_rows:
        importer_raw = row[0].strip()
        skleyka_name = row[1].strip()
        if skleyka_name and skleyka_name not in skleyki_names:
            skleyki_names[skleyka_name] = importer_raw

    # Resolve importer_id: map "ИП"→id, "ООО"→id
    # importer_map keys come from importery.nazvanie (full names like "ИП Медведева П.В.")
    # Build a short-key map: "ИП" → first importer id whose name starts with "ИП"
    def _resolve_importer(raw: str) -> int | None:
        raw_upper = raw.strip().upper()
        for name, imp_id in importer_map.items():
            if name.upper().startswith(raw_upper):
                return imp_id
        return None

    # Load existing skleyki_ozon to avoid duplicates
    existing_skleyki = query_all(conn, "SELECT id, nazvanie FROM skleyki_ozon")
    existing_skleyki_map: dict[str, int] = {r["nazvanie"]: r["id"] for r in existing_skleyki}

    inserted_skleyki = 0
    # Insert missing skleyki
    for skleyka_name, importer_raw in skleyki_names.items():
        if skleyka_name in existing_skleyki_map:
            continue
        importer_id = _resolve_importer(importer_raw)
        if not dry_run:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO skleyki_ozon (nazvanie, importer_id)
                    VALUES (%s, %s)
                    ON CONFLICT (nazvanie) DO NOTHING
                    RETURNING id
                    """,
                    (skleyka_name, importer_id),
                )
                row_result = cur.fetchone()
                if row_result:
                    existing_skleyki_map[skleyka_name] = row_result[0]
            conn.commit()
        else:
            # In dry-run, assign a placeholder id so tovary loop can proceed
            existing_skleyki_map[skleyka_name] = -(inserted_skleyki + 1)
        inserted_skleyki += 1
        log["details"].append({"action": "insert", "level": "skleyki_ozon", "key": skleyka_name})

    # After insert, reload map in case ON CONFLICT suppressed some returns
    if not dry_run:
        existing_skleyki = query_all(conn, "SELECT id, nazvanie FROM skleyki_ozon")
        existing_skleyki_map = {r["nazvanie"]: r["id"] for r in existing_skleyki}

    # Load existing tovary_skleyki_ozon to avoid duplicates
    existing_tovary_links = set()
    if not dry_run:
        for r in query_all(conn, "SELECT tovar_id, skleyka_id FROM tovary_skleyki_ozon"):
            existing_tovary_links.add((r["tovar_id"], r["skleyka_id"]))

    # Build artikul_ozon → tovar_id map from DB
    artikul_ozon_rows = query_all(
        conn,
        """
        SELECT t.id AS tovar_id, a.artikul_ozon
        FROM tovary t
        JOIN artikuly a ON t.artikul_id = a.id
        WHERE a.artikul_ozon IS NOT NULL AND a.artikul_ozon != ''
        """,
    )
    # One artikul_ozon may map to multiple tovary (different sizes)
    artikul_ozon_to_tovar_ids: dict[str, list[int]] = {}
    for r in artikul_ozon_rows:
        key = r["artikul_ozon"].strip()
        artikul_ozon_to_tovar_ids.setdefault(key, []).append(r["tovar_id"])

    inserted_tovary = 0
    skipped = 0

    for row in data_rows:
        skleyka_name = row[1].strip()
        artikul_ozon = row[3].strip()

        skleyka_id = existing_skleyki_map.get(skleyka_name)
        if not skleyka_id or skleyka_id < 0:
            skipped += 1
            continue

        tovar_ids = artikul_ozon_to_tovar_ids.get(artikul_ozon, [])
        if not tovar_ids:
            skipped += 1
            log["warnings"].append(
                f"sync_skleyki_ozon: artikul_ozon '{artikul_ozon}' not found in DB"
            )
            continue

        for tovar_id in tovar_ids:
            if (tovar_id, skleyka_id) in existing_tovary_links:
                continue
            if not dry_run:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO tovary_skleyki_ozon (tovar_id, skleyka_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (tovar_id, skleyka_id),
                    )
                conn.commit()
                existing_tovary_links.add((tovar_id, skleyka_id))
            inserted_tovary += 1

    log["summary"]["skleyki_ozon"] = {
        "inserted_skleyki": inserted_skleyki,
        "inserted_tovary": inserted_tovary,
        "skipped": skipped,
    }
    logger.info(
        f"skleyki_ozon: {inserted_skleyki} new skleyki, "
        f"{inserted_tovary} new tovar links, {skipped} skipped rows"
    )


# --- Orchestrator ---

def run_sync(level: str = "all", dry_run: bool = False, spreadsheet_id: Optional[str] = None):
    """Run the sync pipeline."""
    sid = spreadsheet_id or SPREADSHEET_ID
    start = time.time()

    log = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "spreadsheet_id": sid,
        "dry_run": dry_run,
        "summary": {},
        "details": [],
        "warnings": [],
    }

    mode = "DRY RUN" if dry_run else "APPLY"
    logger.info(f"Sync Sheets → Supabase (level={level}, mode={mode})")
    logger.info("=" * 50)

    # Determine which levels to sync
    if level == "all":
        target_levels = set(LEVELS_ORDER)
    else:
        # Include all levels up to and including the target
        idx = LEVELS_ORDER.index(level) if level in LEVELS_ORDER else -1
        if idx == -1:
            logger.error(f"Unknown level: {level}. Valid: {LEVELS_ORDER}")
            return
        target_levels = set(LEVELS_ORDER[: idx + 1])

    # Connect
    logger.info("Connecting to Supabase...")
    conn = get_supabase_conn()

    logger.info("Loading Google Sheets...")
    gs_client = get_sheets_client()

    sheets_modeli = load_sheet_as_dicts(gs_client, sid, "Все модели")
    sheets_tovary = load_sheet_as_dicts(gs_client, sid, "Все товары")
    logger.info(f"  Все модели: {len(sheets_modeli)} rows")
    logger.info(f"  Все товары: {len(sheets_tovary)} rows")

    # Load raw rows for sheets with empty/merged headers
    skleyki_ozon_rows: list[list[str]] = []
    if "skleyki_ozon" in target_levels:
        skleyki_ozon_rows = load_sheet_as_rows(gs_client, sid, "Склейки Озон")
        logger.info(f"  Склейки Озон: {len(skleyki_ozon_rows)} rows (raw)")

    # Sync levels in order
    cvet_map = {}
    osnova_map = {}
    model_map = {}
    art_map = {}

    if "cveta" in target_levels:
        cvet_map = sync_cveta(conn, sheets_tovary, log, dry_run)
    else:
        # Load existing mappings for FK resolution
        for r in query_all(conn, "SELECT id, color_code FROM cveta"):
            cvet_map[normalize_key(r["color_code"])] = r["id"]

    if "modeli_osnova" in target_levels:
        osnova_map = sync_modeli_osnova(conn, sheets_modeli, log, dry_run)
    else:
        for r in query_all(conn, "SELECT id, kod FROM modeli_osnova"):
            osnova_map[normalize_key(r["kod"])] = r["id"]

    if "modeli" in target_levels:
        model_map = sync_modeli(conn, sheets_modeli, sheets_tovary, osnova_map, log, dry_run)
    else:
        for r in query_all(conn, "SELECT id, kod FROM modeli"):
            model_map[normalize_key(r["kod"])] = r["id"]

    if "artikuly" in target_levels:
        art_map = sync_artikuly(conn, sheets_tovary, model_map, cvet_map, log, dry_run)
    else:
        for r in query_all(conn, "SELECT id, artikul FROM artikuly"):
            art_map[normalize_key(r["artikul"])] = r["id"]

    if "tovary" in target_levels:
        sync_tovary(conn, sheets_tovary, art_map, log, dry_run)

    if "skleyki_ozon" in target_levels:
        importer_map = {r["nazvanie"]: r["id"] for r in query_all(conn, "SELECT id, nazvanie FROM importery")}
        sync_skleyki_ozon(conn, skleyki_ozon_rows, importer_map, log, dry_run)

    conn.close()

    # Duration
    duration = time.time() - start
    log["duration_ms"] = int(duration * 1000)

    # Write JSON log
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "reports")
    os.makedirs(log_dir, exist_ok=True)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_path = os.path.join(log_dir, f"sync-log-{date_str}.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"Log: {log_path}")

    # Print summary
    print()
    print(f"Sync Sheets → Supabase (level: {level}) {'[DRY RUN]' if dry_run else ''}")
    print("━" * 55)
    total_i, total_u, total_d = 0, 0, 0
    for lv in LEVELS_ORDER:
        if lv not in log["summary"]:
            continue
        s = log["summary"][lv]
        if lv == "skleyki_ozon":
            sk = s["inserted_skleyki"]
            tv = s["inserted_tovary"]
            sk_s = s["skipped"]
            print(f"  {lv:20s} {sk:3d} skleyki, {tv:3d} links, {sk_s:3d} skipped")
            total_i += sk + tv
        else:
            i, u, d = s["inserted"], s["updated"], s["soft_deleted"]
            total_i += i
            total_u += u
            total_d += d
            print(f"  {lv:20s} {i:3d} new, {u:3d} updated, {d:3d} archived")
    print("━" * 55)
    print(f"  {'TOTAL':20s} {total_i:3d} new, {total_u:3d} updated, {total_d:3d} archived ({duration:.1f}s)")

    if log["warnings"]:
        print(f"\n⚠ {len(log['warnings'])} warnings (see log)")

    print(f"Log: {log_path}")
    return log


def main():
    parser = argparse.ArgumentParser(description="Sync Google Sheets → Supabase (product matrix)")
    parser.add_argument("--level", default="all", choices=LEVELS_ORDER + ["all"],
                        help="Sync level (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    parser.add_argument("--spreadsheet-id", default=None, help="Override spreadsheet ID")
    args = parser.parse_args()

    run_sync(level=args.level, dry_run=args.dry_run, spreadsheet_id=args.spreadsheet_id)


if __name__ == "__main__":
    main()
