"""Wrapper around `gws sheets +read` (Google Sheets API CLI)."""
from __future__ import annotations

import json
import subprocess
from typing import Any


def read_range(spreadsheet_id: str, sheet_range: str) -> list[list[Any]]:
    """Return values matrix; row 0 is the header."""
    result = subprocess.run(
        ["gws", "sheets", "+read",
         "--spreadsheet", spreadsheet_id,
         "--range", sheet_range],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gws read failed (rc={result.returncode}): {result.stderr}")

    raw = result.stdout
    if raw.startswith("Using keyring"):
        raw = raw.split("\n", 1)[1]
    data = json.loads(raw)
    return data.get("values", [])
