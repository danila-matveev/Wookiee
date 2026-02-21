"""Vasily API — HTTP-эндпоинт для запуска расчёта перестановок WB.

Используется Google Apps Script для запуска из кнопки в Google Sheets.

    POST /run          — запустить расчёт (фоновая задача)
    GET  /status       — текущий статус: idle / running / done / error
    GET  /health       — healthcheck для Docker
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

load_dotenv()

API_KEY = os.getenv("VASILY_API_KEY", "")

app = FastAPI(title="Vasily API", version="1.0.0")
logger = logging.getLogger("vasily_api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

# ── State ────────────────────────────────────────────────────────────────────
_lock = threading.Lock()
_state: dict = {
    "status": "idle",       # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "error": None,
    "summary": None,
}


def _verify_key(x_api_key: str = Header(...)) -> None:
    if not API_KEY:
        raise HTTPException(500, "VASILY_API_KEY not configured on server")
    if x_api_key != API_KEY:
        raise HTTPException(403, "Invalid API key")


# ── Background worker ────────────────────────────────────────────────────────
def _run_reports() -> None:
    """Run Vasily reports for all cabinets (blocking, runs in thread)."""
    from agents.vasily.config import CABINETS, REPORT_PERIOD_DAYS, VASILY_SPREADSHEET_ID
    from agents.vasily.service import VasilyService
    from agents.vasily.sheets_export import export_to_sheets, export_dashboard

    svc = VasilyService()
    summaries = []
    all_results = []

    for cabinet in CABINETS:
        cab = cabinet.strip()
        if not cab:
            continue
        logger.info("Расчёт для %s...", cab)
        result = svc.run_report(cab, days=REPORT_PERIOD_DAYS)
        logger.info(
            "%s: индекс=%.1f%%, перемещений=%d",
            result["cabinet"],
            result["summary"]["overall_index"],
            result["summary"]["movements_count"],
        )

        if VASILY_SPREADSHEET_ID:
            export_to_sheets(result)
            logger.info("Экспорт в Sheets: %s", result["cabinet"])

        all_results.append(result)
        summaries.append({
            "cabinet": result["cabinet"],
            "overall_index": result["summary"]["overall_index"],
            "movements_count": result["summary"]["movements_count"],
            "movements_qty": result["summary"]["movements_qty"],
            "supplies_count": result["summary"]["supplies_count"],
            "supplies_qty": result["summary"]["supplies_qty"],
        })

    # Dashboard on «Обновление» sheet
    if VASILY_SPREADSHEET_ID and all_results:
        try:
            export_dashboard(all_results, REPORT_PERIOD_DAYS)
        except Exception as e:
            logger.error("Ошибка обновления дашборда: %s", e)

    return summaries


def _worker() -> None:
    """Thread target: run reports and update state."""
    try:
        results = _run_reports()
        with _lock:
            _state["status"] = "done"
            _state["finished_at"] = datetime.now().isoformat(timespec="seconds")
            _state["summary"] = results
            _state["error"] = None
    except Exception as exc:
        logger.exception("Ошибка расчёта: %s", exc)
        with _lock:
            _state["status"] = "error"
            _state["finished_at"] = datetime.now().isoformat(timespec="seconds")
            _state["error"] = str(exc)


# ── Endpoints ────────────────────────────────────────────────────────────────
@app.post("/run")
def run_report(x_api_key: str = Header(...)):
    _verify_key(x_api_key)

    with _lock:
        if _state["status"] == "running":
            return JSONResponse(
                status_code=409,
                content={
                    "status": "running",
                    "started_at": _state["started_at"],
                    "message": "Расчёт уже запущен",
                },
            )
        _state["status"] = "running"
        _state["started_at"] = datetime.now().isoformat(timespec="seconds")
        _state["finished_at"] = None
        _state["error"] = None
        _state["summary"] = None

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    return JSONResponse(
        status_code=202,
        content={"status": "running", "started_at": _state["started_at"]},
    )


@app.get("/status")
def get_status(x_api_key: str = Header(...)):
    _verify_key(x_api_key)
    with _lock:
        return dict(_state)


@app.get("/health")
def health():
    return {"ok": True}
