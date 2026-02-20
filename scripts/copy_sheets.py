"""One-time script: copy all _TEST sheets from 'Копия Спецификации' to 'Спецификации'.

Auto-discovers all sheets ending with '_TEST' in the source spreadsheet.

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


def main():
    gc = get_client(GOOGLE_SA_FILE)
    source = gc.open_by_key(SOURCE_ID)

    logger.info("Source: %s", source.title)
    logger.info("Target ID: %s", TARGET_ID)

    copied = 0
    for ws in source.worksheets():
        if not ws.title.endswith("_TEST"):
            continue

        logger.info("Copying '%s' (id=%s) ...", ws.title, ws.id)
        ws.copy_to(TARGET_ID)
        logger.info("  -> copied")
        copied += 1

    logger.info("Done. Copied %d _TEST sheets.", copied)


if __name__ == "__main__":
    main()
