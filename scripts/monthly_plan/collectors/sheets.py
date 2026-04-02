"""Google Sheets data collector: financier plan, KPI targets, external ads."""
import json
import subprocess

# Sheet IDs (stable)
FINANCIER_SHEET_ID = "1Dsz7s_mZ0wUhviGFho89lyhtjce1V0Cmv_RPL1aLxnk"
KPI_SHEET_ID = "1GRCGSAJESSDvAhoVMmXljXy-qErMKt-n45PV96YBiVY"
EXTERNAL_ADS_SHEET_ID = "1PvsgAkb2K84ss4iTD25yoD0pxSZYiVgcqetVUtCBvGg"

# Russian month names for sheet tab lookup
MONTH_NAMES_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}


def _read_sheet(sheet_id: str, range_str: str) -> list:
    """Read Google Sheet range via gws CLI. Returns list of rows."""
    try:
        result = subprocess.run(
            ["gws", "sheets", "get", sheet_id, "--range", range_str, "--format", "json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return []


def collect_sheets(plan_month: str) -> dict:
    """Collect data from Google Sheets: financier plan, KPI, external ads.

    Args:
        plan_month: target month "YYYY-MM" (e.g., "2026-05")
    """
    year, month = map(int, plan_month.split("-"))

    # Base month = plan_month - 1 (for external ads of current period)
    if month == 1:
        base_month_num = 12
    else:
        base_month_num = month - 1
    base_month_name = MONTH_NAMES_RU.get(base_month_num, "")

    # Plan month name (for financier plan)
    plan_month_name = MONTH_NAMES_RU.get(month, "")

    # 1. Financier plan
    financier_wb = _read_sheet(FINANCIER_SHEET_ID, "WB!A1:Z50")
    financier_ozon = _read_sheet(FINANCIER_SHEET_ID, "OZON!A1:Z30")

    # 2. KPI targets
    kpi_data = _read_sheet(KPI_SHEET_ID, "Sheet1!A1:Z20")

    # 3. External ads (base month)
    external_ads_range = f"Итог {base_month_name}!A1:Q40"
    external_ads = _read_sheet(EXTERNAL_ADS_SHEET_ID, external_ads_range)

    return {
        "sheets": {
            "financier_plan": {
                "wb": financier_wb,
                "ozon": financier_ozon,
            },
            "kpi_targets": kpi_data,
            "external_ads_detailed": external_ads,
            "external_ads_month": base_month_name,
        }
    }
