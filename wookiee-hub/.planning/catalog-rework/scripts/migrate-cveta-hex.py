#!/usr/bin/env python3
"""Wave 0 step 9 — fill cveta.hex via name -> hex dictionary lookup.

Non-interactive REST-based migration. Logs to wave_0_cveta_hex.log.

Sources for the lookup name (in order):
  1. cveta.color  (English, primary in current data)
  2. cveta.cvet   (Russian or English fallback)
"""
from __future__ import annotations
import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

ROOT = Path('/Users/danilamatveev/Projects/Wookiee')
PLAN_ROOT = ROOT / 'wookiee-hub' / '.planning' / 'catalog-rework'
LOG_PATH = PLAN_ROOT / 'wave_0_cveta_hex.log'

# ---------------------------------------------------------------------------
# Russian + English color dictionary (lowercase keys, hex values)
# ---------------------------------------------------------------------------
COLOR_DICT_RU: dict[str, str] = {
    'белый': '#FFFFFF', 'кремовый': '#FFF8DC', 'молочный': '#FFFDD0',
    'бежевый': '#F5DEB3', 'светло-бежевый': '#F5F0E1', 'тёмно-бежевый': '#C4A57B',
    'песочный': '#E0C9A6', 'кофейный': '#6F4E37', 'шоколадный': '#5C4033',
    'коричневый': '#8B4513', 'тёмно-коричневый': '#3E2723', 'мокко': '#967259',
    'хаки': '#8B864E', 'оливковый': '#808000', 'болотный': '#556B2F',
    'зелёный': '#228B22', 'мятный': '#98FF98', 'изумрудный': '#50C878',
    'тёмно-зелёный': '#013220', 'фисташковый': '#93C572', 'салатовый': '#A8E04F',
    'голубой': '#87CEEB', 'небесный': '#87CEEB', 'тёмно-голубой': '#4A6E8A',
    'бирюзовый': '#40E0D0', 'циан': '#00FFFF', 'аква': '#00FFFF',
    'синий': '#0000FF', 'тёмно-синий': '#000080', 'тёмно синий': '#000080',
    'индиго': '#4B0082', 'кобальтовый': '#0047AB', 'васильковый': '#6495ED',
    'фиолетовый': '#8B00FF', 'сиреневый': '#C8A2C8', 'лавандовый': '#E6E6FA',
    'пурпурный': '#800080', 'фуксия': '#FF00FF', 'малиновый': '#DC143C',
    'розовый': '#FFC0CB', 'светло-розовый': '#FFB6C1', 'пыльно-розовый': '#D8A6A6',
    'пудровый': '#F5C2C7', 'персиковый': '#FFCBA4', 'коралловый': '#FF7F50',
    'красный': '#FF0000', 'бордовый': '#800020', 'винный': '#722F37',
    'тёмно-красный': '#8B0000', 'кирпичный': '#B22222', 'терракотовый': '#E2725B',
    'оранжевый': '#FFA500', 'тёмно-оранжевый': '#FF8C00', 'абрикосовый': '#FBCEB1',
    'жёлтый': '#FFFF00', 'лимонный': '#FFFACD', 'горчичный': '#FFDB58',
    'золотой': '#FFD700', 'охра': '#CC7722',
    'серый': '#808080', 'светло-серый': '#D3D3D3', 'тёмно-серый': '#404040',
    'тёмно серый': '#404040', 'графитовый': '#383838', 'антрацитовый': '#293133',
    'серебристый': '#C0C0C0', 'жемчужный': '#EAE0C8',
    'чёрный': '#000000', 'черный': '#000000',
    'айвори': '#FFFFF0',
}

COLOR_DICT_EN: dict[str, str] = {
    'white': '#FFFFFF', 'ivory': '#FFFFF0', 'cream': '#FFF8DC', 'milky': '#FFFDD0',
    'beige': '#F5DEB3', 'light beige': '#F5F0E1', 'dark beige': '#C4A57B',
    'darkbeige': '#C4A57B', 'sand': '#E0C9A6', 'coffee': '#6F4E37',
    'chocolate': '#5C4033', 'chocolate washed': '#4A3527',
    'brown': '#8B4513', 'light brown': '#C4A484', 'lightbrown': '#C4A484',
    'dark brown': '#3E2723', 'mocha': '#967259', 'mocco': '#967259',
    'fig': '#5E2750', 'brownie': '#5C4033', 'americano': '#5C3924',
    'khaki': '#8B864E', 'khaki washed': '#7B7438', 'olive': '#808000',
    'olive washed': '#6E6E00', 'swamp': '#556B2F',
    'green': '#228B22', 'mint': '#98FF98', 'emerald': '#50C878',
    'emerald green': '#50C878', 'dark green': '#013220', 'darkgreen': '#013220',
    'forest green': '#228B22', 'pale green': '#98FB98', 'light green': '#90EE90',
    'lightgreen': '#90EE90', 'lime': '#A8E04F', 'shock green': '#39FF14',
    'pistachio': '#93C572', 'military green': '#4B5320',
    'blue': '#0000FF', 'light blue': '#87CEEB', 'sky blue': '#87CEEB',
    'dark blue': '#000080', 'navy blue': '#000080', 'royal blue': '#4169E1',
    'blue 6': '#4682B4', 'blue washed': '#6E8FB2',
    'denim washed': '#3F5673',
    'turquoise': '#40E0D0', 'cyan': '#00FFFF', 'aqua': '#00FFFF',
    'cobalt': '#0047AB', 'cornflower': '#6495ED',
    'violet': '#8B00FF', 'purple': '#800080', 'dark purple': '#4B0082',
    'light purple': '#B19CD9', 'lilacpurple': '#C8A2C8',
    'purple washed': '#6E4C7A',
    'lilac': '#C8A2C8', 'lavender': '#E6E6FA',
    'pink': '#FFC0CB', 'light pink': '#FFB6C1', 'pale pink': '#FADADD',
    'rose pink': '#FF66CC', 'pink orange': '#FF9966',
    'shinny pink': '#FF69B4', 'shiny pink': '#FF69B4',
    'dark pink': '#E75480', 'heart pink': '#FF8DA1',
    'cotton candy washed': '#F4B6C2', 'barbie washed': '#E0218A',
    'powder': '#F5C2C7', 'peach': '#FFCBA4', 'coral': '#FF7F50',
    'red': '#FF0000', 'wine red': '#722F37', 'winered': '#722F37',
    'dark red': '#8B0000', 'date red 2': '#8B0000', 'orange red': '#FF4500',
    'watermelon red': '#E73B3A',
    'brick': '#B22222', 'terracotta': '#E2725B', 'orange': '#FFA500',
    'orange 2': '#FF8C00', 'dark orange': '#FF8C00', 'apricot': '#FBCEB1',
    'yellow': '#FFFF00', 'royal yellow': '#FADA5E', 'bright yellow': '#FFEA00',
    'lemon': '#FFFACD', 'mustard': '#FFDB58',
    'gold': '#FFD700', 'ochre': '#CC7722',
    'grey': '#808080', 'gray': '#808080',
    'light grey': '#D3D3D3', 'silver grey': '#C0C0C0', 'dark grey': '#404040',
    'graphite': '#383838', 'anthracite': '#293133', 'silver': '#C0C0C0',
    'pearl': '#EAE0C8', 'grey washed': '#9A9A9A',
    'black': '#000000', 'black washed': '#1A1A1A',
    'nude': '#E3BC9A', 'skin': '#FFE0BD',
    'storm': '#4F5258', 'obsidian': '#0B1215', 'wineberry': '#591C36',
    'umber': '#635147', 'stone': '#8B8B83', 'affogato': '#5D3A1A',
    'fig': '#5E2750',
}


def normalize(s: str | None) -> str:
    if not s:
        return ''
    return re.sub(r'\s+', ' ', s.strip().lower())


def find_hex(*candidates: str | None) -> str | None:
    for raw in candidates:
        n = normalize(raw)
        if not n:
            continue
        # exact EN
        if n in COLOR_DICT_EN:
            return COLOR_DICT_EN[n]
        # exact RU
        if n in COLOR_DICT_RU:
            return COLOR_DICT_RU[n]
        # word-by-word: try to find any token that matches a single word color
        for tok in re.split(r'[\s,/\-]+', n):
            if not tok:
                continue
            if tok in COLOR_DICT_EN:
                return COLOR_DICT_EN[tok]
            if tok in COLOR_DICT_RU:
                return COLOR_DICT_RU[tok]
        # substring fallback: longest dict key contained in name
        best_key = ''
        best_hex = None
        for key, hx in (*COLOR_DICT_EN.items(), *COLOR_DICT_RU.items()):
            if key in n and len(key) > len(best_key):
                best_key = key
                best_hex = hx
        if best_hex:
            return best_hex
    return None


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


def supabase_request(env: dict[str, str], method: str, path: str,
                     body: dict | None = None,
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

    log(f'=== migrate-cveta-hex started at {datetime.now().isoformat()} ===')

    code, body = supabase_request(env, 'GET',
                                   '/rest/v1/cveta?select=id,color_code,color,cvet,hex&limit=1000')
    if code != 200:
        log(f'ERROR fetching cveta: HTTP {code}: {body!r}')
        return 1
    rows = json.loads(body)
    log(f'Загружено цветов: {len(rows)}')

    found_updates: list[dict] = []
    missed: list[dict] = []
    for r in rows:
        if r.get('hex'):
            continue
        hx = find_hex(r.get('color'), r.get('cvet'))
        if hx:
            found_updates.append({'id': r['id'], 'kod': r.get('color_code'),
                                  'name': r.get('color') or r.get('cvet'), 'hex': hx})
        else:
            missed.append({'id': r['id'], 'kod': r.get('color_code'),
                           'color': r.get('color'), 'cvet': r.get('cvet')})

    log(f'\n=== DRY-RUN: найдено {len(found_updates)}, не найдено {len(missed)} ===')
    log('First 30 matches:')
    for u in found_updates[:30]:
        log(f"  id={u['id']:3} kod={(u['kod'] or '')!s:15} name={(u['name'] or '')!s:25} -> {u['hex']}")
    log('\nMisses:')
    for m in missed:
        log(f"  id={m['id']:3} kod={(m['kod'] or '')!s:18} color={m['color']!r} cvet={m['cvet']!r}")

    log(f'\n=== APPLY {len(found_updates)} updates ===')
    success = 0
    for u in found_updates:
        path = f"/rest/v1/cveta?id=eq.{u['id']}"
        code, resp = supabase_request(env, 'PATCH', path, body={'hex': u['hex']},
                                       extra_headers={'Prefer': 'return=minimal'})
        if 200 <= code < 300:
            success += 1
        else:
            log(f"  FAILED id={u['id']} code={code}: {resp!r}")
    log(f'Обновлено: {success} / {len(found_updates)}')

    # Verify
    code, body = supabase_request(env, 'GET', '/rest/v1/cveta?select=hex&limit=1000')
    nulls = 0
    if code == 200:
        for r in json.loads(body):
            if not r.get('hex'):
                nulls += 1
    log(f'\nVerify: cveta WHERE hex IS NULL = {nulls} (expected ≤30)')

    LOG_PATH.write_text('\n'.join(log_lines), encoding='utf-8')
    log(f'Log saved to {LOG_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
