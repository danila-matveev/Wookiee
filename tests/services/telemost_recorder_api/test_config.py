"""Tests for the Phase 0 config module."""
from __future__ import annotations

import os
from unittest.mock import patch


_REQUIRED_ENV = {
    "TELEMOST_DISABLE_DOTENV": "1",
    "TELEMOST_BOT_TOKEN": "bot:token",
    "TELEMOST_BOT_ID": "12345",
    "TELEMOST_BOT_USERNAME": "wookiee_recorder_bot",
    "TELEMOST_WEBHOOK_SECRET": "secret_xyz",
    "SUPABASE_URL": "https://x.supabase.co",
    "SUPABASE_SERVICE_KEY": "srk",
    "SUPABASE_HOST": "db.example.com",
    "SUPABASE_PORT": "5432",
    "SUPABASE_DB": "postgres",
    "SUPABASE_USER": "postgres",
    "SUPABASE_PASSWORD": "p@ss/word",  # special chars to test URL encoding
    "SPEECHKIT_API_KEY": "sk_key",
    "YANDEX_FOLDER_ID": "folder",
    "OPENROUTER_API_KEY": "or_key",
    "BITRIX24_WEBHOOK_URL": "https://b.example.com/rest/1/abc/",
}


def test_config_reads_required_env_vars():
    with patch.dict(os.environ, _REQUIRED_ENV, clear=True):
        import importlib

        from services.telemost_recorder_api import config

        importlib.reload(config)
        assert config.TELEMOST_BOT_TOKEN == "bot:token"
        assert config.TELEMOST_BOT_ID == 12345
        assert config.TELEMOST_BOT_USERNAME == "wookiee_recorder_bot"
        assert config.TELEMOST_WEBHOOK_SECRET == "secret_xyz"
        assert config.SUPABASE_URL == "https://x.supabase.co"
        assert config.SUPABASE_SERVICE_KEY == "srk"
        assert config.SPEECHKIT_API_KEY == "sk_key"
        assert config.YANDEX_FOLDER_ID == "folder"
        assert config.OPENROUTER_API_KEY == "or_key"
        assert config.BITRIX24_WEBHOOK_URL == "https://b.example.com/rest/1/abc/"
        assert config.MAX_PARALLEL_RECORDINGS == 1
        assert config.AUDIO_RETENTION_DAYS == 30
        assert config.RECORDING_HARD_LIMIT_HOURS == 4


def test_database_url_is_built_from_parts_and_url_encoded():
    with patch.dict(os.environ, _REQUIRED_ENV, clear=True):
        import importlib

        from services.telemost_recorder_api import config

        importlib.reload(config)
        # password "p@ss/word" must be URL-encoded → p%40ss%2Fword
        assert config.DATABASE_URL == (
            "postgresql://postgres:p%40ss%2Fword@db.example.com:5432/postgres?sslmode=require"
        )


def test_config_fails_loudly_on_missing_required():
    with patch.dict(os.environ, {"TELEMOST_DISABLE_DOTENV": "1"}, clear=True):
        import importlib

        from services.telemost_recorder_api import config

        try:
            importlib.reload(config)
        except RuntimeError as e:
            # Exact var doesn't matter — just that one of them surfaces
            assert "Required env var" in str(e)
        else:
            raise AssertionError("expected RuntimeError")


def test_optional_tunables_have_defaults():
    env = {**_REQUIRED_ENV}
    # Remove optional tunables so we test defaults
    with patch.dict(os.environ, env, clear=True):
        import importlib

        from services.telemost_recorder_api import config

        importlib.reload(config)
        assert config.MAX_PARALLEL_RECORDINGS == 1
        assert config.AUDIO_RETENTION_DAYS == 30
        assert config.LLM_POSTPROCESS_MODEL == "google/gemini-2.5-flash"
        assert config.LLM_POSTPROCESS_TIMEOUT_SECONDS == 120
        assert config.LOG_LEVEL == "INFO"


def test_optional_tunables_can_be_overridden():
    env = {**_REQUIRED_ENV, "MAX_PARALLEL_RECORDINGS": "3", "LOG_LEVEL": "DEBUG"}
    with patch.dict(os.environ, env, clear=True):
        import importlib

        from services.telemost_recorder_api import config

        importlib.reload(config)
        assert config.MAX_PARALLEL_RECORDINGS == 3
        assert config.LOG_LEVEL == "DEBUG"


def test_default_timeouts():
    """Без env-override все 4 таймаута берут дефолты."""
    with patch.dict(os.environ, _REQUIRED_ENV, clear=True):
        import importlib

        from services.telemost_recorder_api import config

        importlib.reload(config)
        assert config.TELEGRAM_TIMEOUT_SECONDS == 60.0
        assert config.NOTION_TIMEOUT_SECONDS == 30.0
        assert config.BITRIX_TIMEOUT_SECONDS == 15.0
        assert config.SUPABASE_STORAGE_TIMEOUT_SECONDS == 120.0


def test_timeout_overrides_via_env():
    """Любой из 4 таймаутов конфигурируется через env-переменную."""
    env = {
        **_REQUIRED_ENV,
        "TELEGRAM_TIMEOUT_SECONDS": "45",
        "NOTION_TIMEOUT_SECONDS": "20",
        "BITRIX_TIMEOUT_SECONDS": "10",
        "SUPABASE_STORAGE_TIMEOUT_SECONDS": "240",
    }
    with patch.dict(os.environ, env, clear=True):
        import importlib

        from services.telemost_recorder_api import config

        importlib.reload(config)
        assert config.TELEGRAM_TIMEOUT_SECONDS == 45.0
        assert config.NOTION_TIMEOUT_SECONDS == 20.0
        assert config.BITRIX_TIMEOUT_SECONDS == 10.0
        assert config.SUPABASE_STORAGE_TIMEOUT_SECONDS == 240.0
