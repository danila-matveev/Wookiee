MODEL_OSNOVA_MAPPING = {
    "vuki": "Vuki", "vuki2": "Vuki", "vuki 2": "Vuki", "vukiw": "Vuki", "vuki w": "Vuki", "vukiw2": "Vuki", "vuki w2": "Vuki", "vukin": "Vuki", "vukin2": "Vuki", "vukin 2": "Vuki", "vukip": "Vuki", "vuki p": "Vuki", "компбел-ж-бесшов": "Vuki",
    "moon": "Moon", "moon2": "Moon", "moon 2": "Moon", "moonw": "Moon", "moon w": "Moon", "moonw2": "Moon", "moon w2": "Moon",
    "ruby": "Ruby", "rubyw": "Ruby", "ruby w": "Ruby", "rubyp": "Ruby", "ruby p": "Ruby",
    "joy": "Joy", "joyw": "Joy", "joy w": "Joy",
    "wendy": "Wendy",
    "bella": "Bella",
    "audrey": "Audrey",
    "alice": "Alice",
    "mia": "Other",
    "miafull": "Other",
    "space": "Other",
    "valery": "Valery",
    "duo": "Other",
    "angelina": "Other",
    "amanda slip": "Other", "amanda thong": "Other", "amanda": "Other",
    "olivia": "Olivia",
    "roxy": "Roxy",
    "set vuki": "Set Vuki", "set vukip": "Set Vuki", "set vuki p": "Set Vuki", "set wookiee": "Set Vuki", "set vuki2": "Set Vuki", "set vuki 2": "Set Vuki",
    "set moon": "Set Moon", "set moon2": "Set Moon", "set moon 2": "Set Moon", "set moonp": "Set Moon", "set moon p": "Set Moon",
    "set bella": "Set Bella",
    "set wendy": "Set Wendy",
    "set ruby": "Set Ruby"
}

# Модели, подтверждённо выводимые (бизнес-правило).
# Переопределяет статус из БД, если он устарел.
# Ключи — raw model names (до MODEL_OSNOVA_MAPPING), lowercase.
# Удалить / обновить после актуализации статусов в Supabase.
KNOWN_PHASING_OUT = {
    "olivia", "roxy",
    "mia", "miafull", "space", "duo", "angelina",
    "amanda", "amanda slip", "amanda thong",
}

# Подмодели трикотажной коллекции: raw → display name.
# Позволяет разбить Vuki на Vuki / Vuki-N / Vuki-W / Vuki-P и т.д.
SUBMODEL_MAPPING = {
    # Vuki
    "vuki": "Vuki", "vuki2": "Vuki", "vuki 2": "Vuki", "компбел-ж-бесшов": "Vuki",
    "vukin": "Vuki-N", "vukin2": "Vuki-N", "vukin 2": "Vuki-N",
    "vukiw": "Vuki-W", "vuki w": "Vuki-W", "vukiw2": "Vuki-W", "vuki w2": "Vuki-W",
    "vukip": "Vuki-P", "vuki p": "Vuki-P",
    # Moon
    "moon": "Moon", "moon2": "Moon", "moon 2": "Moon",
    "moonw": "Moon-W", "moon w": "Moon-W", "moonw2": "Moon-W", "moon w2": "Moon-W",
    # Ruby
    "ruby": "Ruby",
    "rubyw": "Ruby-W", "ruby w": "Ruby-W",
    "rubyp": "Ruby-P", "ruby p": "Ruby-P",
    # Joy
    "joy": "Joy",
    "joyw": "Joy-W", "joy w": "Joy-W",
}

# Модели трикотажной коллекции (osnova-уровень).
KNITWEAR_MODELS = {"Vuki", "Moon", "Ruby", "Joy"}


def map_to_submodel(model_name: str) -> str:
    """Maps a raw model name to sub-model display name (e.g. vukin → Vuki-N)."""
    if not model_name:
        return "Unknown"
    norm = model_name.lower().strip().replace('_', ' ')
    return SUBMODEL_MAPPING.get(norm, model_name.capitalize())


def get_submodel_sql(raw_column: str) -> str:
    """Returns SQL CASE expression mapping raw DB column to sub-model name."""
    sql = ["CASE"]
    target_to_keys = {}
    for k, v in SUBMODEL_MAPPING.items():
        k_clean = k.replace('_', ' ').replace("'", "''")
        if v not in target_to_keys:
            target_to_keys[v] = []
        target_to_keys[v].append(f"'{k_clean}'")
    for target_val, keys in target_to_keys.items():
        keys_str = ", ".join(keys)
        sql.append(f"  WHEN REPLACE(LOWER(TRIM({raw_column})), '_', ' ') IN ({keys_str}) THEN '{target_val}'")
    sql.append(f"  ELSE INITCAP(LOWER(TRIM(REPLACE({raw_column}, '_', ' '))))")
    sql.append("END")
    return "\n".join(sql)


def map_to_osnova(model_name: str) -> str:
    """Takes a raw model name (potentially with underscores) and returns model_osnova."""
    if not model_name:
        return "Unknown"
    norm = model_name.lower().strip().replace('_', ' ')
    return MODEL_OSNOVA_MAPPING.get(norm, model_name.capitalize())


# Reverse mapping: osnova → primary raw key (first key that maps to each osnova).
_OSNOVA_TO_RAW: dict[str, str] = {}
for _k, _v in MODEL_OSNOVA_MAPPING.items():
    if _v not in _OSNOVA_TO_RAW:
        _OSNOVA_TO_RAW[_v] = _k


def map_from_osnova(osnova_name: str) -> str:
    """Reverse mapping: model_osnova → raw model name for DB queries.

    Returns the primary raw key (e.g. "Set Wendy" → "set wendy").
    If no mapping exists, returns lowercase of input.
    """
    return _OSNOVA_TO_RAW.get(osnova_name, osnova_name.lower())

def get_osnova_sql(raw_column: str) -> str:
    """Returns a SQL CASE expression to map a raw DB column directly to model_osnova."""
    # We do LOWER(TRIM(REPLACE(col, '_', ' '))) to map set_vuki2 -> set vuki2
    sql = ["CASE"]
    
    # Pre-group values by target model for optimized IN clauses
    target_to_keys = {}
    for k, v in MODEL_OSNOVA_MAPPING.items():
        k_clean = k.replace('_', ' ').replace("'", "''")
        if v not in target_to_keys:
            target_to_keys[v] = []
        target_to_keys[v].append(f"'{k_clean}'")
        
    for target_val, keys in target_to_keys.items():
        keys_str = ", ".join(keys)
        sql.append(f"  WHEN REPLACE(LOWER(TRIM({raw_column})), '_', ' ') IN ({keys_str}) THEN '{target_val}'")
        
    sql.append(f"  ELSE INITCAP(LOWER(TRIM(REPLACE({raw_column}, '_', ' '))))")
    sql.append("END")
    
    return "\n".join(sql)
