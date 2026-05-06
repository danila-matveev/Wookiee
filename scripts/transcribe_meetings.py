"""
Извлечение транскрипций из PDF, прикреплённых к карточкам в Notion-БД
"Записи встреч", и запись полного текста в тело страницы.

PDF в карточках — это уже готовые субтитры с таймкодами (не нужен OCR/STT,
только текстовое извлечение через pypdf).

Использование:
    # Тестовый прогон на одной случайной карточке (по умолчанию):
    python scripts/transcribe_meetings.py

    # На конкретной странице:
    python scripts/transcribe_meetings.py --page-id <uuid>

    # Поиск по подстроке в названии:
    python scripts/transcribe_meetings.py --title-contains "Планерка"

    # Перезаписать существующую транскрипцию:
    python scripts/transcribe_meetings.py --page-id <uuid> --overwrite

    # Только показать что нашлось, без записи:
    python scripts/transcribe_meetings.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from io import BytesIO
from pathlib import Path

import httpx
from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.config import NOTION_TOKEN  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("transcribe_meetings")

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
MEETINGS_DATABASE_ID = "34e58a2bd58780ed9d48ed21a5ac6b94"

TRANSCRIPT_TOGGLE_TITLE = "📜 Полная транскрипция"
FILE_PROPERTY_NAMES = ("Full file", "File", "Файл", "Файлы")

# Лимиты Notion API
MAX_RICH_TEXT_LEN = 1900   # запас от 2000
MAX_BLOCKS_PER_REQUEST = 100


# ─────────────────────────────────────────────────────────────────────────────
# Notion HTTP
# ─────────────────────────────────────────────────────────────────────────────

class NotionAPI:
    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=60, headers=self.headers)

    async def close(self):
        await self.client.aclose()

    async def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        url = f"{NOTION_API}/{path}"
        resp = await self.client.request(method, url, json=json)
        if resp.status_code >= 400:
            logger.error("Notion %s %s → %d: %s", method, path, resp.status_code, resp.text[:400])
            resp.raise_for_status()
        return resp.json()

    async def query_database(self, database_id: str, *, page_size: int = 100) -> list[dict]:
        results: list[dict] = []
        cursor: str | None = None
        while True:
            payload: dict = {"page_size": page_size}
            if cursor:
                payload["start_cursor"] = cursor
            data = await self._request("POST", f"databases/{database_id}/query", payload)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return results

    async def get_page(self, page_id: str) -> dict:
        return await self._request("GET", f"pages/{page_id}")

    async def get_block_children(self, block_id: str) -> list[dict]:
        results: list[dict] = []
        cursor: str | None = None
        while True:
            path = f"blocks/{block_id}/children?page_size=100"
            if cursor:
                path += f"&start_cursor={cursor}"
            data = await self._request("GET", path)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return results

    async def append_block_children(self, block_id: str, children: list[dict]) -> list[dict]:
        created: list[dict] = []
        for i in range(0, len(children), MAX_BLOCKS_PER_REQUEST):
            batch = children[i:i + MAX_BLOCKS_PER_REQUEST]
            data = await self._request(
                "PATCH", f"blocks/{block_id}/children", {"children": batch}
            )
            created.extend(data.get("results", []))
        return created

    async def delete_block(self, block_id: str) -> None:
        await self._request("DELETE", f"blocks/{block_id}")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: разбор Notion-страницы
# ─────────────────────────────────────────────────────────────────────────────

def get_page_title(page: dict) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            parts = prop.get("title", [])
            return "".join(p.get("plain_text", "") for p in parts).strip()
    return "(без названия)"


def get_pdf_files(page: dict) -> list[tuple[str, str]]:
    """Возвращает список (имя_файла, signed_url) из любого files-property."""
    props = page.get("properties", {})

    # Сначала пытаемся в известных именах
    candidates = [props[name] for name in FILE_PROPERTY_NAMES if name in props]
    # Иначе любое property типа files
    if not candidates:
        candidates = [p for p in props.values() if p.get("type") == "files"]

    files_out: list[tuple[str, str]] = []
    for prop in candidates:
        for f in prop.get("files", []):
            name = f.get("name", "file.pdf")
            if f.get("type") == "file":
                url = f.get("file", {}).get("url", "")
            else:
                url = f.get("external", {}).get("url", "")
            if url and name.lower().endswith(".pdf"):
                files_out.append((name, url))
    return files_out


# ─────────────────────────────────────────────────────────────────────────────
# PDF
# ─────────────────────────────────────────────────────────────────────────────

async def download_pdf(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    pages_text: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            logger.warning("Не удалось прочитать страницу %d: %s", i, e)
            text = ""
        pages_text.append(text.strip())
    return "\n\n".join(t for t in pages_text if t)


# ─────────────────────────────────────────────────────────────────────────────
# Notion blocks: текст → toggle с параграфами
# ─────────────────────────────────────────────────────────────────────────────

def _chunk(s: str, n: int) -> list[str]:
    return [s[i:i + n] for i in range(0, len(s), n)] if s else [""]


def _paragraph_block(text: str) -> dict:
    """Один paragraph-блок с rich_text, разбитым на runs <= MAX_RICH_TEXT_LEN."""
    runs = [
        {"type": "text", "text": {"content": chunk}}
        for chunk in _chunk(text, MAX_RICH_TEXT_LEN)
    ] or [{"type": "text", "text": {"content": ""}}]
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": runs},
    }


def text_to_paragraph_blocks(text: str) -> list[dict]:
    """Разбиваем текст на параграфы по двойным переносам, каждый — отдельный блок."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return [_paragraph_block("(пустой текст)")]
    return [_paragraph_block(p) for p in paragraphs]


def transcript_toggle_block() -> dict:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [
                {"type": "text", "text": {"content": TRANSCRIPT_TOGGLE_TITLE}}
            ],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Поиск существующего toggle в теле страницы
# ─────────────────────────────────────────────────────────────────────────────

async def find_existing_transcript_toggle(api: NotionAPI, page_id: str) -> str | None:
    blocks = await api.get_block_children(page_id)
    for b in blocks:
        if b.get("type") != "toggle":
            continue
        rt = b.get("toggle", {}).get("rich_text", [])
        title = "".join(r.get("plain_text", "") for r in rt).strip()
        if title == TRANSCRIPT_TOGGLE_TITLE:
            return b["id"]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Основная логика
# ─────────────────────────────────────────────────────────────────────────────

async def process_page(
    api: NotionAPI,
    page: dict,
    *,
    dry_run: bool,
    overwrite: bool,
) -> bool:
    page_id = page["id"]
    title = get_page_title(page)
    page_url = page.get("url", "")
    logger.info("─── %s", title)
    logger.info("    %s", page_url)

    pdfs = get_pdf_files(page)
    if not pdfs:
        logger.warning("    ⏭  PDF не прикреплён")
        return False

    if len(pdfs) > 1:
        logger.info("    Найдено PDF: %d, беру первый", len(pdfs))
    pdf_name, pdf_url = pdfs[0]
    logger.info("    📎 %s", pdf_name)

    existing_toggle = await find_existing_transcript_toggle(api, page_id)
    if existing_toggle and not overwrite:
        logger.info("    ✓ Транскрипция уже есть — пропускаю (--overwrite чтобы перезаписать)")
        return False

    logger.info("    ⬇  Скачиваю PDF…")
    data = await download_pdf(pdf_url)
    logger.info("    %.1f KB", len(data) / 1024)

    logger.info("    📖 Извлекаю текст…")
    text = extract_pdf_text(data)
    text = text.strip()
    if not text:
        logger.error("    ✗ Текст пустой — возможно, PDF из изображений (нужен OCR)")
        return False

    chars = len(text)
    paragraphs = text_to_paragraph_blocks(text)
    logger.info("    %d символов, %d параграфов", chars, len(paragraphs))

    preview = text[:500].replace("\n", " ⏎ ")
    logger.info("    Превью: %s…", preview)

    if dry_run:
        logger.info("    🔍 dry-run — записи не делаю")
        return True

    if existing_toggle and overwrite:
        logger.info("    🗑  Удаляю старый toggle…")
        await api.delete_block(existing_toggle)

    logger.info("    📝 Создаю toggle и пишу %d параграфов…", len(paragraphs))
    created = await api.append_block_children(page_id, [transcript_toggle_block()])
    toggle_id = created[0]["id"]
    await api.append_block_children(toggle_id, paragraphs)
    logger.info("    ✅ Готово: %s", page_url)
    return True


async def select_page(
    api: NotionAPI,
    *,
    page_id: str | None,
    title_contains: str | None,
    limit: int,
    overwrite: bool,
) -> list[dict]:
    if page_id:
        return [await api.get_page(page_id)]

    pages = await api.query_database(MEETINGS_DATABASE_ID)
    logger.info("В БД %d карточек", len(pages))

    if title_contains:
        needle = title_contains.lower()
        pages = [p for p in pages if needle in get_page_title(p).lower()]
        logger.info("По фильтру title~'%s': %d", title_contains, len(pages))

    pages = [p for p in pages if get_pdf_files(p)]
    logger.info("С PDF: %d", len(pages))

    if not overwrite:
        out: list[dict] = []
        for p in pages:
            existing = await find_existing_transcript_toggle(api, p["id"])
            if not existing:
                out.append(p)
            if len(out) >= limit:
                break
        logger.info("Без транскрипции (отобрано %d): %d", limit, len(out))
        return out

    return pages[:limit]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-id", help="UUID конкретной страницы")
    parser.add_argument("--title-contains", help="Подстрока в названии")
    parser.add_argument("--limit", type=int, default=1, help="Сколько карточек обработать (по умолчанию: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Без записи в Notion")
    parser.add_argument("--overwrite", action="store_true", help="Перезаписать существующий toggle")
    args = parser.parse_args()

    if not NOTION_TOKEN:
        logger.error("NOTION_TOKEN не задан в .env")
        return 1

    api = NotionAPI(NOTION_TOKEN)
    try:
        pages = await select_page(
            api,
            page_id=args.page_id,
            title_contains=args.title_contains,
            limit=args.limit,
            overwrite=args.overwrite,
        )
        if not pages:
            logger.warning("Нет подходящих страниц")
            return 0

        logger.info("Обрабатываю %d страниц(ы)…", len(pages))
        ok = 0
        for page in pages:
            try:
                if await process_page(api, page, dry_run=args.dry_run, overwrite=args.overwrite):
                    ok += 1
            except Exception as e:
                logger.exception("Ошибка на странице %s: %s", page.get("id"), e)

        logger.info("Готово: %d/%d", ok, len(pages))
        return 0
    finally:
        await api.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
