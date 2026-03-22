"""
Content Knowledge Base configuration.

Reads from .env via shared pattern. DB connection reuses Supabase env vars.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')

# Yandex Disk
YANDEX_DISK_TOKEN: str = os.getenv('YANDEX_DISK_TOKEN', '')
YANDEX_DISK_ROOT: str = os.getenv('YANDEX_DISK_ROOT', '/Wookiee/Контент/2025')

# Gemini Embedding
GOOGLE_API_KEY: str = os.getenv('GOOGLE_API_KEY', '')
EMBEDDING_MODEL: str = 'gemini-embedding-2-preview'
EMBEDDING_DIMENSIONS: int = 3072  # Max for multimodal image embeddings

# Supabase connection (same as knowledge_base)
POSTGRES_HOST: str = os.getenv('POSTGRES_HOST', os.getenv('SUPABASE_HOST', 'localhost'))
POSTGRES_PORT: int = int(os.getenv('POSTGRES_PORT', os.getenv('SUPABASE_PORT', '5432')))
POSTGRES_DB: str = os.getenv('POSTGRES_DB', os.getenv('SUPABASE_DB', 'postgres'))
POSTGRES_USER: str = os.getenv('POSTGRES_USER', os.getenv('SUPABASE_USER', 'postgres'))
POSTGRES_PASSWORD: str = os.getenv('POSTGRES_PASSWORD', os.getenv('SUPABASE_PASSWORD', ''))

# Indexer settings
INDEX_DELAY: float = 1.0  # Seconds between embedding requests
MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024  # Resize images above 10MB
MAX_IMAGE_DIMENSION: int = 4096  # Max px on longest side after resize

# Skipped categories (not indexed in phase 1)
SKIP_CATEGORIES: set = {'видео', 'исходники'}
