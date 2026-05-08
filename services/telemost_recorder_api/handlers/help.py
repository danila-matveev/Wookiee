"""/help command."""
from __future__ import annotations

from services.telemost_recorder_api.telegram_client import tg_send_message

_HELP = """*Wookiee Recorder — справка*

`/record <ссылка>` — поставить встречу в очередь записи. Поддерживаются ссылки `telemost.yandex.ru/j/...` и `telemost.360.yandex.ru/j/...`.

`/status` — твои активные записи (`queued` / `recording` / `postprocessing`) и 5 последних завершённых.

`/list` — 10 последних встреч, где ты триггерщик/организатор/инвайт.

После завершения записи я пришлю в DM:
• краткий summary с темами, решениями и задачами
• полный transcript как `.txt` attachment

Аудио хранится 30 дней, текст — бессрочно.
"""


async def handle_help(chat_id: int) -> None:
    await tg_send_message(chat_id, _HELP)
