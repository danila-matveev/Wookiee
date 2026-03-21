"""
Bitrix24 REST API client with OAuth2 support.

Supports two modes:
1. Webhook mode (simple, current) — uses static webhook URL
2. OAuth2 mode (full access) — uses access_token + refresh_token

Usage:
    # Webhook mode (backward compatible)
    client = BitrixClient.from_webhook(os.getenv('Bitrix_rest_api'))

    # OAuth2 mode
    client = BitrixClient.from_oauth(
        domain='wookiee.bitrix24.ru',
        client_id='...',
        client_secret='...',
        tokens_file='path/to/tokens.json',
    )
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Rate limiting: Bitrix24 allows 2 req/sec for webhooks
_REQUEST_INTERVAL = 0.5
_MAX_RETRIES = 3
_RETRY_WAIT = 5


class BitrixClient:
    """Universal Bitrix24 REST API client."""

    def __init__(
        self,
        base_url: str,
        *,
        domain: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        tokens_file: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ):
        self._base_url = base_url.rstrip('/')
        self._domain = domain
        self._client_id = client_id
        self._client_secret = client_secret
        self._tokens_file = tokens_file
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._session = requests.Session()
        self._last_request_time = 0.0
        self._is_oauth = bool(client_id)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_webhook(cls, webhook_url: str) -> 'BitrixClient':
        """Create client from webhook URL (simple mode)."""
        return cls(base_url=webhook_url)

    @classmethod
    def from_oauth(
        cls,
        domain: str,
        client_id: str,
        client_secret: str,
        tokens_file: str | None = None,
    ) -> 'BitrixClient':
        """Create client from OAuth2 credentials."""
        tokens = {}
        if tokens_file and Path(tokens_file).exists():
            with open(tokens_file) as f:
                tokens = json.load(f)

        access_token = tokens.get('access_token', '')
        refresh_token = tokens.get('refresh_token', '')
        base_url = f'https://{domain}/rest/'

        client = cls(
            base_url=base_url,
            domain=domain,
            client_id=client_id,
            client_secret=client_secret,
            tokens_file=tokens_file,
            access_token=access_token,
            refresh_token=refresh_token,
        )

        # If we have a refresh token but expired access token, refresh now
        if refresh_token and not access_token:
            client._do_refresh()

        return client

    @classmethod
    def from_env(cls) -> 'BitrixClient':
        """Create client from environment variables.

        Uses OAuth2 if BITRIX_CLIENT_ID is set, otherwise webhook.
        """
        from shared.config import PROJECT_ROOT
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / '.env')

        client_id = os.getenv('BITRIX_CLIENT_ID', '')
        if client_id:
            return cls.from_oauth(
                domain=os.getenv('BITRIX_DOMAIN', 'wookiee.bitrix24.ru'),
                client_id=client_id,
                client_secret=os.getenv('BITRIX_CLIENT_SECRET', ''),
                tokens_file=str(PROJECT_ROOT / '.bitrix_tokens.json'),
            )
        else:
            webhook = os.getenv('Bitrix_rest_api', '')
            if not webhook:
                raise ValueError('No Bitrix credentials: set Bitrix_rest_api or BITRIX_CLIENT_ID')
            return cls.from_webhook(webhook)

    # ------------------------------------------------------------------
    # OAuth2 flow
    # ------------------------------------------------------------------

    def get_auth_url(self) -> str:
        """Get URL for user to authorize the app (step 1 of OAuth2)."""
        if not self._client_id:
            raise ValueError('OAuth2 not configured — use from_oauth()')
        return (
            f'https://{self._domain}/oauth/authorize/'
            f'?client_id={self._client_id}'
            f'&response_type=code'
        )

    def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for tokens (step 2 of OAuth2)."""
        resp = requests.get(
            f'https://oauth.bitrix.info/oauth/token/',
            params={
                'grant_type': 'authorization_code',
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'code': code,
            },
        )
        data = resp.json()
        if 'access_token' not in data:
            raise ValueError(f'Token exchange failed: {data}')

        self._access_token = data['access_token']
        self._refresh_token = data['refresh_token']
        self._save_tokens(data)
        logger.info('OAuth2 tokens obtained and saved')
        return data

    def _do_refresh(self) -> None:
        """Refresh expired access token."""
        if not self._refresh_token:
            raise ValueError('No refresh token available')

        logger.info('Refreshing Bitrix24 access token...')
        resp = requests.get(
            f'https://oauth.bitrix.info/oauth/token/',
            params={
                'grant_type': 'refresh_token',
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'refresh_token': self._refresh_token,
            },
        )
        data = resp.json()
        if 'access_token' not in data:
            raise ValueError(f'Token refresh failed: {data}')

        self._access_token = data['access_token']
        self._refresh_token = data['refresh_token']
        self._save_tokens(data)
        logger.info('Token refreshed successfully')

    def _save_tokens(self, data: dict) -> None:
        """Persist tokens to file."""
        if not self._tokens_file:
            return
        tokens = {
            'access_token': data.get('access_token', ''),
            'refresh_token': data.get('refresh_token', ''),
            'expires_in': data.get('expires_in', 3600),
            'domain': self._domain,
            'member_id': data.get('member_id', ''),
            'saved_at': time.time(),
        }
        with open(self._tokens_file, 'w') as f:
            json.dump(tokens, f, indent=2)

    # ------------------------------------------------------------------
    # Core API methods
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < _REQUEST_INTERVAL:
            time.sleep(_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def call(self, method: str, params: dict | None = None) -> Any:
        """Call a single Bitrix24 REST API method."""
        self._rate_limit()

        if self._is_oauth:
            url = f'{self._base_url}/{method}'
            p = dict(params or {})
            p['auth'] = self._access_token
        else:
            url = f'{self._base_url}/{method}'
            p = dict(params or {})

        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._session.post(url, json=p, timeout=30)

                if resp.status_code == 429:
                    wait = _RETRY_WAIT * (attempt + 1)
                    logger.warning(f'Rate limited, waiting {wait}s...')
                    time.sleep(wait)
                    continue

                if resp.status_code in (502, 503, 504):
                    logger.warning(f'Server error {resp.status_code}, retry {attempt + 1}')
                    time.sleep(_RETRY_WAIT)
                    continue

                data = resp.json()

                # Handle expired token
                if data.get('error') == 'expired_token' and self._is_oauth:
                    self._do_refresh()
                    p['auth'] = self._access_token
                    continue

                if 'error' in data and data['error'] != '':
                    raise ValueError(f'Bitrix API error: {data}')

                return data.get('result', data)

            except requests.ConnectionError:
                logger.warning(f'Connection error, retry {attempt + 1}')
                time.sleep(_RETRY_WAIT)
                self._session = requests.Session()

        raise ConnectionError(f'Failed after {_MAX_RETRIES} retries: {method}')

    def call_all(
        self,
        method: str,
        params: dict | None = None,
        result_key: str | None = None,
    ) -> list:
        """Call API method with automatic pagination. Returns all results."""
        all_results = []
        p = dict(params or {})
        p['start'] = 0

        while True:
            self._rate_limit()

            if self._is_oauth:
                url = f'{self._base_url}/{method}'
                p_send = dict(p)
                p_send['auth'] = self._access_token
            else:
                url = f'{self._base_url}/{method}'
                p_send = dict(p)

            for attempt in range(_MAX_RETRIES):
                try:
                    resp = self._session.post(url, json=p_send, timeout=30)
                    if resp.status_code in (429, 502, 503, 504):
                        time.sleep(_RETRY_WAIT * (attempt + 1))
                        continue
                    data = resp.json()

                    if data.get('error') == 'expired_token' and self._is_oauth:
                        self._do_refresh()
                        p_send['auth'] = self._access_token
                        continue

                    break
                except requests.ConnectionError:
                    time.sleep(_RETRY_WAIT)
                    self._session = requests.Session()
            else:
                raise ConnectionError(f'Failed after retries: {method}')

            result = data.get('result', [])
            if result_key and isinstance(result, dict):
                result = result.get(result_key, [])

            if isinstance(result, list):
                all_results.extend(result)
            elif isinstance(result, dict):
                all_results.append(result)

            # Check for next page
            next_start = data.get('next')
            if next_start is None:
                break
            p['start'] = next_start

        return all_results

    # ------------------------------------------------------------------
    # High-level methods
    # ------------------------------------------------------------------

    def check_scope(self) -> list[str]:
        """Return list of available API scopes."""
        return self.call('scope')

    def get_users(self) -> list[dict]:
        """Get all active users."""
        return self.call_all('user.get', {'ACTIVE': True})

    def get_current_user(self) -> dict:
        """Get current authenticated user info."""
        return self.call('user.current')

    # -- Knowledge Base (Landing) --

    def kb_get_sites(self) -> list[dict]:
        """Get all knowledge base sites."""
        return self.call_all('landing.site.getlist', {
            'filter': {'TYPE': 'KNOWLEDGE'},
        })

    def kb_get_pages(self, site_id: int) -> list[dict]:
        """Get all pages in a knowledge base."""
        return self.call_all('landing.landing.getlist', {
            'filter': {'SITE_ID': site_id},
        })

    def kb_get_blocks(self, page_id: int) -> list[dict]:
        """Get content blocks for a page."""
        return self.call_all('landing.block.getlist', {
            'lid': page_id,
        })

    def kb_get_block_content(self, block_id: int) -> dict:
        """Get content of a specific block."""
        return self.call('landing.block.getcontent', {
            'block': block_id,
        })

    def kb_add_page(self, site_id: int, title: str) -> int:
        """Create a new page in knowledge base. Returns page ID."""
        result = self.call('landing.landing.add', {
            'fields': {
                'SITE_ID': site_id,
                'TITLE': title,
            },
        })
        return result

    def kb_add_block(self, page_id: int, block_code: str, content: dict | None = None) -> int:
        """Add a content block to a page."""
        params = {
            'lid': page_id,
            'code': block_code,
        }
        if content:
            params['content'] = content
        return self.call('landing.landing.addblock', params)

    def kb_update_block_content(self, block_id: int, content: dict) -> bool:
        """Update content of a block."""
        return self.call('landing.block.updatenodes', {
            'block': block_id,
            'data': content,
        })

    # -- Tasks --

    def get_tasks(self, params: dict | None = None) -> list[dict]:
        """Get tasks with pagination."""
        return self.call_all('tasks.task.list', params, result_key='tasks')

    # -- Chat / IM --

    def send_message(self, chat_id: str, message: str) -> dict:
        """Send a message to a chat."""
        return self.call('im.message.add', {
            'DIALOG_ID': chat_id,
            'MESSAGE': message,
        })
