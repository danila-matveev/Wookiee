#!/usr/bin/env python3
"""Wave 0 step 10 — fill modeli_osnova.status_id from Google Sheet 'Все модели'.

Non-interactive. Logs to wave_0_model_statuses.log next to the planning folder.

Sheet: 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg, worksheet "Все модели".
Columns: tries to match either 'Модель' or 'kod'/'Артикул' for the model name,
and 'Статус' for the status.
Maps status_name -> statusy.id WHERE tip='model'.
"""
from __future__ import annotations
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

import gspread

ROOT = Path('/Users/danilamatveev/Projects/Wookiee')
PLAN_ROOT = ROOT / 'wookiee-hub' / '.planning' / 'catalog-rework'
LOG_PATH = PLAN_ROOT / 'wave_0_model_statuses.log'
SA_PATH = ROOT / 'services' / 'sheets_sync' / 'credentials' / 'google_sa.json'
SHEET_ID = '19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg'

MODEL_COL_CANDIDATES = ['Модель', 'модель', 'kod', 'Артикул', 'артикул']
STATUS_COL_CANDIDATES = ['Статус', 'статус', 'Status']


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for p in [ROOT / 'database' / 'sku' / '.env', ROOT / '.env']:
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def supabase_request(env, method, path, body=None, extra_headers=None):
    url = env['SUPABASE_URL'].rstrip('/') + path
    headers = {
        'apikey': env['SUPABASE_SERVICE_KEY'],
        'Authorization': f"Bearer {env['SUPABASE_SERVICE_KEY']}",
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def find_col_index(hdr: list[str], candidates: list[str]) -> int | None:
    for cand in candidates:
        for i, h in enumerate(hdr):
            if h.strip().lower() == cand.strip().lower():
                return i
    return None


def main() -> int:
    log_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        log_lines.append(msg)

    log(f'=== sync-model-statuses started at {datetime.now().isoformat()} ===')

    env = load_env()
    gc = gspread.service_account(filename=str(SA_PATH))
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet('Все модели')

    rows = ws.get_all_values()
    if not rows:
        log('Лист "Все модели" пуст')
        LOG_PATH.write_text('\n'.join(log_lines), encoding='utf-8')
        return 1
    hdr = rows[0]
    log(f'Заголовки: {hdr}')

    kod_idx = find_col_index(hdr, MODEL_COL_CANDIDATES)
    status_idx = find_col_index(hdr, STATUS_COL_CANDIDATES)
    if kod_idx is None or status_idx is None:
        log(f'Не нашли нужные колонки: kod_idx={kod_idx}, status_idx={status_idx}')
        LOG_PATH.write_text('\n'.join(log_lines), encoding='utf-8')
        return 1
    log(f'kod_idx={kod_idx} ({hdr[kod_idx]!r}), status_idx={status_idx} ({hdr[status_idx]!r})')

    sheet_mapping: dict[str, str] = {}
    for r in rows[1:]:
        if len(r) <= max(kod_idx, status_idx):
            continue
        kod = (r[kod_idx] or '').strip()
        status = (r[status_idx] or '').strip()
        if kod and status:
            sheet_mapping[kod] = status
    log(f'Маппинг из Sheet: {len(sheet_mapping)} моделей')

    # Fetch model-status records
    code, body = supabase_request(env, 'GET',
                                   '/rest/v1/statusy?select=id,nazvanie,tip&tip=eq.model')
    if code != 200:
        log(f'ERROR fetching model statuses: HTTP {code}: {body!r}')
        return 1
    status_records = json.loads(body)
    status_id_by_name = {s['nazvanie']: s['id'] for s in status_records}
    log(f'Model-статусы в Supabase: {status_id_by_name}')

    # Fetch all modeli_osnova kod -> id (case-insensitive lookup)
    code, body = supabase_request(env, 'GET', '/rest/v1/modeli_osnova?select=id,kod&limit=1000')
    if code != 200:
        log(f'ERROR fetching modeli_osnova: HTTP {code}: {body!r}')
        return 1
    db_models = json.loads(body)
    db_kod_to_id: dict[str, int] = {}
    db_kod_lower_to_id: dict[str, int] = {}
    for m in db_models:
        if m.get('kod'):
            db_kod_to_id[m['kod']] = m['id']
            db_kod_lower_to_id[m['kod'].lower()] = m['id']
    log(f'Моделей в БД: {len(db_kod_to_id)}')

    # Apply
    updated = 0
    not_in_db: list[tuple[str, str]] = []
    unknown_status: list[tuple[str, str]] = []
    for kod_sheet, status_name in sheet_mapping.items():
        sid = status_id_by_name.get(status_name)
        if not sid:
            unknown_status.append((kod_sheet, status_name))
            continue
        # Try exact, then case-insensitive
        target_id = db_kod_to_id.get(kod_sheet) or db_kod_lower_to_id.get(kod_sheet.lower())
        if not target_id:
            not_in_db.append((kod_sheet, status_name))
            continue
        path = f"/rest/v1/modeli_osnova?id=eq.{target_id}"
        code, _resp = supabase_request(env, 'PATCH', path, body={'status_id': sid},
                                        extra_headers={'Prefer': 'return=minimal'})
        if 200 <= code < 300:
            updated += 1
        else:
            log(f"  FAILED kod={kod_sheet!r} -> status_id={sid}: HTTP {code}: {_resp!r}")

    log(f'\nОбновлено: {updated}')
    log(f'Не нашли в БД: {len(not_in_db)}')
    for k, s in not_in_db:
        log(f'  Sheet kod {k!r} status {s!r} — нет в БД (модель ещё не заведена)')
    log(f'Неизвестный статус (нет в statusy с tip=model): {len(unknown_status)}')
    for k, s in unknown_status:
        log(f'  Sheet kod {k!r} status {s!r} — статус не нашёлся')

    # Verify
    code, body = supabase_request(env, 'GET',
                                   '/rest/v1/modeli_osnova?select=id,kod,status_id&limit=1000')
    if code == 200:
        models = json.loads(body)
        without_status = [m for m in models if m.get('status_id') is None]
        log(f'\nVerify: моделей без status_id осталось: {len(without_status)}')
        for m in without_status:
            log(f'  id={m["id"]:3} kod={m["kod"]!r} — НЕТ В Sheet (NULL status, нужно решение)')

    LOG_PATH.write_text('\n'.join(log_lines), encoding='utf-8')
    log(f'Log saved to {LOG_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
