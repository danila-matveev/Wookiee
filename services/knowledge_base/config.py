"""
Knowledge Base configuration.

Reads from .env via shared pattern. DB connection reuses sku_database/config/database.py.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')

# Gemini Embedding
GOOGLE_API_KEY: str = os.getenv('GOOGLE_API_KEY', '')
EMBEDDING_MODEL: str = os.getenv('EMBEDDING_MODEL', 'gemini-embedding-2-preview')
EMBEDDING_DIMENSIONS: int = int(os.getenv('EMBEDDING_DIMENSIONS', '768'))

# Knowledge source (ingested into pgvector; originals on Google Drive)
KB_SOURCE_DIR: str = os.getenv('KB_SOURCE_DIR', '')

# Supabase connection (reuse sku_database env vars)
POSTGRES_HOST: str = os.getenv('POSTGRES_HOST', os.getenv('SUPABASE_HOST', 'localhost'))
POSTGRES_PORT: int = int(os.getenv('POSTGRES_PORT', os.getenv('SUPABASE_PORT', '5432')))
POSTGRES_DB: str = os.getenv('POSTGRES_DB', os.getenv('SUPABASE_DB', 'postgres'))
POSTGRES_USER: str = os.getenv('POSTGRES_USER', os.getenv('SUPABASE_USER', 'postgres'))
POSTGRES_PASSWORD: str = os.getenv('POSTGRES_PASSWORD', os.getenv('SUPABASE_PASSWORD', ''))

# Embedding batch settings
EMBED_BATCH_SIZE: int = 20  # Small batches to stay within Gemini free tier TPM
EMBED_MAX_CONCURRENT: int = 1  # Sequential to avoid rate limits
EMBED_BATCH_DELAY: float = 2.0  # Seconds between batches

# Chunking
CHUNK_SIZE: int = 1500
CHUNK_OVERLAP: int = 200
