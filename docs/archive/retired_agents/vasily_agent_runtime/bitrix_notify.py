"""Bitrix24 chat notification for Vasily localization reports."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

import requests

from agents.vasily.config import BITRIX_WEBHOOK_URL, BITRIX_CHAT_ID, BITRIX_FOLDER_ID

logger = logging.getLogger(__name__)


class BitrixAPIError(Exception):
    """Ошибка Bitrix24 API."""


class VasilyBitrixNotifier:
    """Sends localization report summaries to a Bitrix24 chat."""

    def __init__(
        self,
        webhook_url: str = "",
        chat_id: str = "",
        folder_id: str = "",
    ):
        self.webhook_url = (webhook_url or BITRIX_WEBHOOK_URL).rstrip("/") + "/"
        self.chat_id = chat_id or BITRIX_CHAT_ID
        self.folder_id = folder_id or BITRIX_FOLDER_ID
        self._session = requests.Session()
        self._last_request_time: float = 0

    # ------------------------------------------------------------------
    # Low-level API
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request_time = time.time()

    def _call(self, method: str, params: dict | None = None) -> dict:
        self._rate_limit()
        url = f"{self.webhook_url}{method}"
        resp = self._session.post(url, json=params or {})
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2))
            logger.warning("Bitrix rate limit, waiting %ds", retry_after)
            time.sleep(retry_after)
            return self._call(method, params)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise BitrixAPIError(data.get("error_description", data["error"]))
        return data

    def _call_upload(self, method: str, file_path: str, params: dict | None = None) -> dict:
        """POST with multipart file upload."""
        self._rate_limit()
        url = f"{self.webhook_url}{method}"
        path = Path(file_path)
        with open(path, "rb") as f:
            files = {"file": (path.name, f)}
            resp = self._session.post(url, data=params or {}, files=files)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2))
            time.sleep(retry_after)
            return self._call_upload(method, file_path, params)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise BitrixAPIError(data.get("error_description", data["error"]))
        return data

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    def send_message(self, text: str) -> dict:
        """Send a text message to the configured Bitrix24 chat."""
        if not self.chat_id:
            logger.warning("VASILY_BITRIX_CHAT_ID не задан — сообщение не отправлено")
            return {}
        return self._call("im.message.add", {
            "DIALOG_ID": self.chat_id,
            "MESSAGE": text,
        })

    def upload_file(self, file_path: str) -> int | None:
        """Upload file to Bitrix24 disk folder, return file ID."""
        if not self.folder_id:
            logger.info("VASILY_BITRIX_FOLDER_ID не задан — файл не загружен")
            return None
        try:
            data = self._call_upload(
                "disk.folder.uploadfile",
                file_path,
                {"id": self.folder_id},
            )
            file_id = data.get("result", {}).get("ID")
            logger.info("Файл загружен в Bitrix: ID=%s", file_id)
            return int(file_id) if file_id else None
        except Exception as e:
            logger.error("Ошибка загрузки файла в Bitrix: %s", e)
            return None

    def send_file_message(self, file_id: int) -> dict:
        """Send a message with an attached file to chat."""
        return self._call("im.message.add", {
            "DIALOG_ID": self.chat_id,
            "MESSAGE": "",
            "ATTACH": [
                {"FILE": [
                    [file_id, ""],
                ]},
            ],
        })

    # ------------------------------------------------------------------
    # Report notification
    # ------------------------------------------------------------------

    def notify_report(self, result: dict, sheets_url: str = "") -> None:
        """Format and send the full report notification to Bitrix chat."""
        if not self.chat_id:
            logger.warning("VASILY_BITRIX_CHAT_ID не задан — уведомление не отправлено")
            return

        text = self._format_message(result, sheets_url)

        try:
            self.send_message(text)
            logger.info("Отправлено уведомление в Bitrix для %s", result.get("cabinet"))
        except Exception as e:
            logger.error("Ошибка отправки сообщения в Bitrix: %s", e)

        # Upload Excel file
        report_path = result.get("report_path", "")
        if report_path and Path(report_path).exists():
            file_id = self.upload_file(report_path)
            if file_id:
                try:
                    self.send_file_message(file_id)
                except Exception as e:
                    logger.error("Ошибка отправки файла в Bitrix-чат: %s", e)

    def _format_message(self, result: dict, sheets_url: str) -> str:
        """Format BBCode message for Bitrix24 chat."""
        cabinet = result.get("cabinet", "?")
        summary = result.get("summary", {})
        regions = result.get("regions", [])
        top_problems = result.get("top_problems", [])
        comparison = result.get("comparison")

        now = datetime.now()
        date_str = now.strftime("%d.%m.%Y %H:%M")

        # Index with delta
        index = summary.get("overall_index", 0)
        delta_str = ""
        if comparison:
            change = comparison.get("index_change", 0)
            delta_str = f" ({change:+.1f} п.п.)"

        lines = [
            f"[B]Отчёт по локализации — {cabinet}[/B]",
            date_str,
            "",
            f"[B]Индекс: {index}%[/B]{delta_str}",
            "",
            f"Перемещений: {summary.get('movements_count', 0)} "
            f"({summary.get('movements_qty', 0)} шт.) | "
            f"Допоставок: {summary.get('supplies_count', 0)} "
            f"({summary.get('supplies_qty', 0)} шт.)",
            "",
        ]

        # Regions
        if regions:
            lines.append("[B]Регионы:[/B]")
            for r in regions:
                name = r.get("region", "")
                idx = r.get("index", 0)
                lines.append(f"  {name}: {idx}%")
            lines.append("")

        # Top 3 problems
        if top_problems:
            lines.append("[B]Топ-3 проблемных SKU:[/B]")
            for i, p in enumerate(top_problems[:3], 1):
                article = p.get("article", "")
                size = p.get("size", "")
                idx = p.get("index", 0)
                lines.append(f"{i}. {article} {size} — {idx}%")
            lines.append("")

        if sheets_url:
            lines.append(f"Google Sheets: {sheets_url}")

        return "\n".join(lines)
