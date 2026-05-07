#!/usr/bin/env python3
"""Wave 0 step 8 — fill cveta.semeystvo + cveta.semeystvo_id by color_code prefix rule.

Non-interactive. Logs to wave_0_cveta_semeystvo.log next to this script's parent.

Mapping:
  AU*           -> audrey
  WE*           -> jelly
  w<digits>     -> jelly  (e.g. w1, w3.5, w11)
  set_*         -> sets
  111, 123, 124, 125 -> sets
  digits-only   -> tricot
  others        -> other
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path('/Users/danilamatveev/Projects/Wookiee')
PLAN_ROOT = ROOT / 'wookiee-hub' / '.planning' / 'catalog-rework'
LOG_PATH = PLAN_ROOT / 'wave_0_cveta_semeystvo.log'


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


def detect_family(color_code: str | None) -> str:
    cc = (color_code or '').strip()
    if not cc:
        return 'other'
    if cc.startswith('AU'):
        return 'audrey'
    if cc.startswith('WE'):
        return 'jelly'
    # w1, w3.5, w11 — Jelly (pure-numeric tail after 'w')
    if cc.startswith('w') and len(cc) > 1:
        tail = cc[1:].replace('.', '')
        if tail and tail.isdigit():
            return 'jelly'
    if cc.startswith('set_') or cc.startswith('set ') or cc in ('111', '123', '124', '125'):
        return 'sets'
    if cc.replace('.', '').isdigit():
        return 'tricot'
    return 'other'


def supabase_request(env: dict[str, str], method: str, path: str, body: dict | None = None,
                     extra_headers: dict[str, str] | None = None) -> tuple[int, bytes]:
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


def main() -> int:
    env = load_env()
    log_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        log_lines.append(msg)

    log(f'=== migrate-cveta-semeystvo started at {datetime.now().isoformat()} ===')

    # Fetch families map
    code, body = supabase_request(env, 'GET', '/rest/v1/semeystva_cvetov?select=id,kod')
    if code != 200:
        log(f'ERROR fetching semeystva_cvetov: HTTP {code}: {body!r}')
        return 1
    fam_to_id = {r['kod']: r['id'] for r in json.loads(body)}
    log(f'Семейства: {fam_to_id}')

    # Fetch all cveta rows
    code, body = supabase_request(env, 'GET',
                                   '/rest/v1/cveta?select=id,color_code,semeystvo,semeystvo_id&limit=1000')
    if code != 200:
        log(f'ERROR fetching cveta: HTTP {code}: {body!r}')
        return 1
    rows = json.loads(body)
    log(f'Загружено цветов: {len(rows)}')

    # Compute updates (DRY-RUN log)
    updates: list[dict] = []
    for r in rows:
        fam = detect_family(r.get('color_code'))
        target_id = fam_to_id.get(fam)
        if r.get('semeystvo') != fam or r.get('semeystvo_id') != target_id:
            updates.append({
                'id': r['id'],
                'kod': r.get('color_code'),
                'old_text': r.get('semeystvo'),
                'old_id': r.get('semeystvo_id'),
                'new_text': fam,
                'new_id': target_id,
            })

    log(f'\n=== DRY-RUN: к обновлению {len(updates)} цветов ===')
    for u in updates:
        log(f"  id={u['id']:3} code={(u['kod'] or '')!s:15} "
            f"{u['old_text'] or 'NULL'} -> {u['new_text']}")

    # Apply updates via PATCH
    log(f'\n=== APPLY {len(updates)} updates ===')
    success = 0
    for u in updates:
        path = f"/rest/v1/cveta?id=eq.{u['id']}"
        body_payload = {'semeystvo': u['new_text'], 'semeystvo_id': u['new_id']}
        code, resp = supabase_request(env, 'PATCH', path, body=body_payload,
                                       extra_headers={'Prefer': 'return=minimal'})
        if 200 <= code < 300:
            success += 1
        else:
            log(f"  FAILED id={u['id']} code={code}: {resp!r}")

    log(f'Обновлено: {success} / {len(updates)}')

    # Verify distribution
    dist: dict[str, int] = {}
    code, body = supabase_request(env, 'GET',
                                   '/rest/v1/cveta?select=semeystvo&limit=1000')
    if code == 200:
        for r in json.loads(body):
            k = r.get('semeystvo') or 'NULL'
            dist[k] = dist.get(k, 0) + 1
    log(f'\nDistribution: {dist}')

    LOG_PATH.write_text('\n'.join(log_lines), encoding='utf-8')
    log(f'\nLog saved to {LOG_PATH}')
    return 0 if success == len(updates) else 2


if __name__ == '__main__':
    sys.exit(main())
