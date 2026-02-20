"""One-time script: copy sheets from 'Копия Спецификации' to 'Спецификации'.

Usage:
    python -m scripts.copy_sheets
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.clients.sheets_client import get_client
from services.sheets_sync.config import GOOGLE_SA_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

SOURCE_ID = "1WMfhIKf5qgmCGu8ypnbEEfdjNgkYhzs8hmEnRBajn2o"  # Копия Спецификации
TARGET_ID = "19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg"  # Спецификации

SHEETS_TO_COPY = [
    "WB остатки",
    "WB Цены",
    "Ozon остатки и цены",
    "МойСклад_АПИ",
    "Отзывы ООО",
    "Отзывы ИП",
    "Фин данные",
]


def main():
    gc = get_client(GOOGLE_SA_FILE)
    source = gc.open_by_key(SOURCE_ID)

    logger.info("Source: %s", source.title)
    logger.info("Target ID: %s", TARGET_ID)

    for name in SHEETS_TO_COPY:
        try:
            ws = source.worksheet(name)
        except Exception:
            logger.warning("Sheet '%s' not found in source, skipping", name)
            continue

        logger.info("Copying '%s' (id=%s) ...", name, ws.id)
        ws.copy_to(TARGET_ID)
        logger.info("  -> copied (will appear as 'Copy of %s')", name)

    logger.info("Done. Rename copied sheets in the target spreadsheet as needed.")


if __name__ == "__main__":
    main()
