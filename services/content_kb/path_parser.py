"""
Parse Yandex Disk path into content metadata.

Extracts year, content_category, model_name, color, and sku
from the folder structure.
"""

from __future__ import annotations

import re

# Known model names (case-insensitive matching)
_KNOWN_MODELS = {
    'alice', 'audrey', 'bella', 'charlotte', 'eva', 'joy', 'lana',
    'miafull', 'moon', 'ruby', 'space', 'valery', 'vuki', 'wendy',
}

# Set variants: set_Bella, Set Moon, etc.
_SET_PATTERN = re.compile(r'^set[_ ]', re.IGNORECASE)

# Category mapping: normalized folder name → content_category
_CATEGORY_MAP = {
    'все фото': 'фото',
    'видео': 'видео',
    'исходники': 'исходники',
    'дизайн': 'дизайн',
    'маркетплейсы': 'маркетплейсы',
    'сайт': 'сайт',
    'аб тесты': 'аб_тесты',
    'lamoda': 'lamoda',
}

# Year pattern
_YEAR_RE = re.compile(r'\b(20\d{2})\b')

# Numbered folder: "5. МАРКЕТПЛЕЙСЫ" → "маркетплейсы"
_NUMBERED_FOLDER_RE = re.compile(r'^\d+\.\s*(.+)$')

# SKU: pure numeric folder name, 6-12 digits
_SKU_RE = re.compile(r'^\d{6,12}$')


def _strip_numbering(folder: str) -> str:
    """Strip leading number prefix: '5. МАРКЕТПЛЕЙСЫ' → 'МАРКЕТПЛЕЙСЫ'."""
    m = _NUMBERED_FOLDER_RE.match(folder)
    return m.group(1).strip() if m else folder


def _detect_category(folder: str) -> str | None:
    """Map a folder name to a content_category."""
    cleaned = _strip_numbering(folder).lower().rstrip()
    return _CATEGORY_MAP.get(cleaned)


def _is_known_model(name: str) -> bool:
    """Check if name is a known model (with or without set_ prefix)."""
    if _SET_PATTERN.match(name):
        # Extract base model from set variant: set_Bella → bella
        base = re.sub(r'^set[_ ]', '', name, flags=re.IGNORECASE)
        return base.lower() in _KNOWN_MODELS
    return name.lower() in _KNOWN_MODELS


def _extract_color(folder: str, model_name: str) -> str | None:
    """Extract color from compound folder name like 'Bella-black' → 'black'."""
    if not model_name:
        return None
    # Pattern: ModelName-color (e.g., Bella-black, set_Bella-white)
    prefix = model_name + '-'
    if folder.startswith(prefix) and len(folder) > len(prefix):
        return folder[len(prefix):]
    # Case-insensitive fallback
    prefix_lower = prefix.lower()
    if folder.lower().startswith(prefix_lower) and len(folder) > len(prefix):
        return folder[len(prefix_lower):]
    return None


def parse_path_metadata(path: str) -> dict:
    """
    Parse a Yandex Disk path into metadata dict.

    Returns dict with keys: year, content_category, model_name, color, sku.
    Missing values are None.
    """
    result = {
        'year': None,
        'content_category': None,
        'model_name': None,
        'color': None,
        'sku': None,
    }

    # Extract year
    year_match = _YEAR_RE.search(path)
    if year_match:
        result['year'] = int(year_match.group(1))

    # Special case: /Блогеры/ root
    if '/Блогеры/' in path or path.startswith('Блогеры/'):
        result['content_category'] = 'блогеры'

    # Split path into components
    parts = [p for p in path.split('/') if p]

    current_model = None

    for part in parts:
        # Detect category from numbered folders
        if result['content_category'] is None:
            cat = _detect_category(part)
            if cat:
                result['content_category'] = cat
                continue

        # Detect SKU (pure numeric folder)
        if _SKU_RE.match(part):
            result['sku'] = part
            continue

        # Detect model name
        if _is_known_model(part):
            current_model = part
            # Normalize set variants to use underscore
            if _SET_PATTERN.match(current_model):
                current_model = re.sub(r'^(set)[_ ]', r'\1_', current_model, flags=re.IGNORECASE)
                # Preserve original casing of the base name
                base = current_model.split('_', 1)[1] if '_' in current_model else current_model
                for known in _KNOWN_MODELS:
                    if base.lower() == known:
                        break
            result['model_name'] = current_model
            continue

        # Try to extract color from compound name (ModelName-color)
        if current_model:
            color = _extract_color(part, current_model)
            if color:
                result['color'] = color
                continue

    return result
