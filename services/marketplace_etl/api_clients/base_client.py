"""
Base API client with rate limiting, retry and exponential backoff.
"""

import time
import logging
import requests


class BaseAPIClient:
    """Base HTTP client with rate limiting and retry logic."""

    def __init__(self, min_interval_sec=1.0, max_retries=5, timeout=30):
        self.min_interval_sec = min_interval_sec
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_request_time = 0.0
        self.logger = logging.getLogger(self.__class__.__name__)

    def _rate_limit(self):
        """Enforce minimum interval between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_interval_sec:
            wait = self.min_interval_sec - elapsed
            self.logger.debug(f"Rate limit: waiting {wait:.2f}s")
            time.sleep(wait)
        self._last_request_time = time.time()

    def _request(self, method, url, headers=None, params=None, json_data=None):
        """
        Make HTTP request with rate limiting, retry and exponential backoff.

        Args:
            method: 'GET' or 'POST'
            url: Request URL
            headers: HTTP headers
            params: Query parameters (for GET)
            json_data: JSON body (for POST)

        Returns:
            Parsed JSON response

        Raises:
            requests.exceptions.HTTPError: After max retries exhausted
        """
        for attempt in range(self.max_retries):
            self._rate_limit()
            try:
                if method == 'GET':
                    response = requests.get(
                        url, params=params, headers=headers, timeout=self.timeout
                    )
                else:
                    response = requests.post(
                        url, json=json_data, headers=headers, timeout=self.timeout
                    )

                if response.status_code == 429:
                    wait = min(2 ** attempt, 60)
                    self.logger.warning(
                        f"429 Rate limited on {url}, waiting {wait}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait)
                    continue

                if response.status_code >= 500 and attempt < self.max_retries - 1:
                    wait = min(2 ** attempt, 30)
                    self.logger.warning(
                        f"{response.status_code} Server error on {url}, retrying in {wait}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait)
                    continue

                response.raise_for_status()

                self.logger.debug(f"{method} {url} -> {response.status_code}")
                return response.json()

            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    wait = min(2 ** attempt, 30)
                    self.logger.warning(
                        f"Timeout on {url}, retrying in {wait}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait)
                    continue
                raise

            except requests.exceptions.ConnectionError:
                if attempt < self.max_retries - 1:
                    wait = min(2 ** attempt, 30)
                    self.logger.warning(
                        f"Connection error on {url}, retrying in {wait}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait)
                    continue
                raise

        raise requests.exceptions.HTTPError(
            f"Max retries ({self.max_retries}) exhausted for {url}"
        )
