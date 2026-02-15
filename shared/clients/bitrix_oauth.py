"""
OAuth 2.0 client for Bitrix24 REST API.

Merged from Bitrix/config.py + Bitrix/client.py.
"""

import json
import os
import time
import logging
import requests
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

from shared.config import PROJECT_ROOT

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class BitrixConfig:
    """Bitrix24 connection configuration."""

    portal_domain: str = os.getenv('BITRIX_PORTAL_DOMAIN', '')
    client_id: str = os.getenv('BITRIX_CLIENT_ID', '')
    client_secret: str = os.getenv('BITRIX_CLIENT_SECRET', '')
    redirect_uri: str = os.getenv('BITRIX_REDIRECT_URI', 'http://localhost:8000/callback')
    tokens_file: str = str(PROJECT_ROOT / '.bitrix_tokens.json')

    @property
    def oauth_authorize_url(self) -> str:
        return f"https://{self.portal_domain}/oauth/authorize/"

    @property
    def oauth_token_url(self) -> str:
        return "https://oauth.bitrix.info/oauth/token/"

    @property
    def rest_api_url(self) -> str:
        return f"https://{self.portal_domain}/rest/"

    def validate(self) -> bool:
        required = [self.portal_domain, self.client_id, self.client_secret]
        return all(required)

    def get_missing_fields(self) -> list:
        missing = []
        if not self.portal_domain:
            missing.append('BITRIX_PORTAL_DOMAIN')
        if not self.client_id:
            missing.append('BITRIX_CLIENT_ID')
        if not self.client_secret:
            missing.append('BITRIX_CLIENT_SECRET')
        return missing


config = BitrixConfig()


# ============================================================================
# Exceptions
# ============================================================================

class BitrixAuthError(Exception):
    """Bitrix24 authorization error."""
    pass


class BitrixAPIError(Exception):
    """Bitrix24 API error."""
    pass


# ============================================================================
# Client
# ============================================================================

class BitrixClient:
    """
    OAuth 2.0 client for Bitrix24 REST API.

    Supports:
    - OAuth 2.0 authorization
    - Automatic token refresh
    - Rate limiting (2 req/sec)
    - File-based token storage
    """

    def __init__(self):
        self.config = config
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.expires_at: Optional[datetime] = None
        self._session = requests.Session()
        self._last_request_time: float = 0
        self._load_tokens()

    def get_auth_url(self) -> str:
        if not self.config.validate():
            missing = self.config.get_missing_fields()
            raise BitrixAuthError(
                f"Missing .env settings: {', '.join(missing)}"
            )
        from urllib.parse import urlencode
        params = {
            'client_id': self.config.client_id,
            'redirect_uri': self.config.redirect_uri,
            'response_type': 'code',
        }
        return f"{self.config.oauth_authorize_url}?{urlencode(params)}"

    def authorize(self, code: str) -> Dict[str, Any]:
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'redirect_uri': self.config.redirect_uri,
            'code': code
        }
        response = self._session.post(self.config.oauth_token_url, data=data)
        if response.status_code != 200:
            raise BitrixAuthError(f"Authorization error: {response.text}")
        tokens = response.json()
        if 'error' in tokens:
            raise BitrixAuthError(f"Error: {tokens.get('error_description', tokens['error'])}")
        self._update_tokens(tokens)
        self._save_tokens()
        logger.info("Bitrix authorized, tokens saved to %s", self.config.tokens_file)
        return tokens

    def refresh_tokens(self) -> Dict[str, Any]:
        if not self.refresh_token:
            raise BitrixAuthError("No refresh token. Re-authorize.")
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'refresh_token': self.refresh_token
        }
        response = self._session.post(self.config.oauth_token_url, data=data)
        if response.status_code != 200:
            raise BitrixAuthError(f"Token refresh error: {response.text}")
        tokens = response.json()
        if 'error' in tokens:
            raise BitrixAuthError(f"Error: {tokens.get('error_description', tokens['error'])}")
        self._update_tokens(tokens)
        self._save_tokens()
        return tokens

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._ensure_valid_token()
        self._rate_limit()
        url = f"{self.config.rest_api_url}{method}"
        request_params = params.copy() if params else {}
        request_params['auth'] = self.access_token
        response = self._session.post(url, json=request_params)
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 2))
            logger.warning("Bitrix rate limit, waiting %ds...", retry_after)
            time.sleep(retry_after)
            return self.call(method, params)
        if response.status_code != 200:
            raise BitrixAPIError(f"API error ({response.status_code}): {response.text}")
        result = response.json()
        if 'error' in result:
            raise BitrixAPIError(f"API error: {result.get('error_description', result['error'])}")
        return result

    def is_authorized(self) -> bool:
        return self.access_token is not None

    def _update_tokens(self, tokens: Dict[str, Any]):
        self.access_token = tokens['access_token']
        self.refresh_token = tokens['refresh_token']
        expires_in = tokens.get('expires_in', 3600)
        self.expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

    def _ensure_valid_token(self):
        if not self.access_token:
            raise BitrixAuthError("No token. Authorize first.")
        if self.expires_at and datetime.now() >= self.expires_at:
            logger.info("Bitrix token expired, refreshing...")
            self.refresh_tokens()

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        min_interval = 0.5
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def _save_tokens(self):
        data = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
        with open(self.config.tokens_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_tokens(self):
        tokens_path = Path(self.config.tokens_file)
        if not tokens_path.exists():
            return
        try:
            with open(tokens_path, 'r') as f:
                data = json.load(f)
            self.access_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')
            if data.get('expires_at'):
                self.expires_at = datetime.fromisoformat(data['expires_at'])
        except (json.JSONDecodeError, KeyError):
            pass
