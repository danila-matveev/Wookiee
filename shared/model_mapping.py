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

def map_to_osnova(model_name: str) -> str:
    """Takes a raw model name (potentially with underscores) and returns model_osnova."""
    if not model_name:
        return "Unknown"
    norm = model_name.lower().strip().replace('_', ' ')
    return MODEL_OSNOVA_MAPPING.get(norm, model_name.capitalize())

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
