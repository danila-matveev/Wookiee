# agents/reporter/bot/handlers.py
"""Telegram command handlers."""
from __future__ import annotations

import logging
from datetime import date

from aiogram import Dispatcher, types
from aiogram.filters import Command

from agents.reporter.bot.keyboards import playbook_review_keyboard
from agents.reporter.types import ReportType, compute_scope

logger = logging.getLogger(__name__)


def register_handlers(dp: Dispatcher, state, gate_checker) -> None:
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer(
            "Reporter V4 Bot\n\n"
            "/status — статус отчётов\n"
            "/run <type> — запустить отчёт\n"
            "/rules — активные правила\n"
            "/pending — паттерны на ревью\n"
            "/health — состояние системы\n"
            "/logs <type> — последние runs"
        )

    @dp.message(Command("status"))
    async def cmd_status(message: types.Message):
        today = date.today()
        runs = state.get_today_status(today)
        if not runs:
            await message.answer(f"📅 {today}: нет запусков")
            return

        lines = [f"📅 <b>Статус отчётов {today}</b>\n"]
        for r in runs:
            status_emoji = {"success": "✅", "failed": "❌", "error": "💥", "pending": "⏳"}.get(r["status"], "🔄")
            lines.append(f"{status_emoji} {r['report_type']}: {r['status']} (attempt {r.get('attempt', 1)})")

        await message.answer("\n".join(lines), parse_mode="HTML")

    @dp.message(Command("run"))
    async def cmd_run(message: types.Message):
        from agents.reporter.pipeline import run_pipeline

        args = message.text.split()[1:] if message.text else []
        if not args:
            types_list = "\n".join(f"  {rt.value}" for rt in ReportType)
            await message.answer(f"Usage: /run <type> [date]\n\nTypes:\n{types_list}")
            return

        try:
            rt = ReportType(args[0])
        except ValueError:
            await message.answer(f"Unknown type: {args[0]}")
            return

        target_date = date.today()
        if len(args) > 1:
            try:
                target_date = date.fromisoformat(args[1])
            except ValueError:
                await message.answer(f"Invalid date: {args[1]}")
                return

        await message.answer(f"⏳ Генерирую {rt.human_name} за {target_date}...")
        scope = compute_scope(rt, target_date)
        result = await run_pipeline(scope, state)

        if result.success:
            await message.answer(
                f"✅ {rt.human_name} готов!\n"
                f"Confidence: {result.confidence:.0%}\n"
                f"Notion: {result.notion_url or 'N/A'}"
            )
        else:
            await message.answer(f"❌ Ошибка: {result.error or result.issues}")

    @dp.message(Command("rules"))
    async def cmd_rules(message: types.Message):
        rules = state.get_active_rules()
        if not rules:
            await message.answer("Нет активных правил")
            return
        lines = [f"📋 <b>Активные правила ({len(rules)})</b>\n"]
        for r in rules[:15]:
            source = "🤖" if r.get("source") == "llm_discovered" else "✍️"
            lines.append(f"{source} {r['rule_text'][:100]}")
        await message.answer("\n".join(lines), parse_mode="HTML")

    @dp.message(Command("pending"))
    async def cmd_pending(message: types.Message):
        pending = state._sb.table("analytics_rules").select("*").eq(
            "status", "pending_review"
        ).execute().data

        if not pending:
            await message.answer("Нет паттернов на ревью")
            return

        for p in pending[:5]:
            text = (
                f"🔍 <b>Новый паттерн</b>\n\n"
                f"{p['rule_text']}\n\n"
                f"Confidence: {p.get('confidence', 0):.0%}\n"
                f"Доказательства: {p.get('evidence', 'N/A')}"
            )
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=playbook_review_keyboard(p["id"]),
            )

    @dp.message(Command("health"))
    async def cmd_health(message: types.Message):
        from agents.reporter.analyst import analyst

        cb = analyst._circuit_breaker
        gate_result = gate_checker.check_both()

        lines = [
            "<b>🏥 Health Check</b>\n",
            f"Circuit Breaker: {cb.state.value} (failures: {cb.failure_count})",
            f"Gates: {'✅ PASS' if gate_result.can_generate else '❌ BLOCKED'}",
        ]
        for g in gate_result.gates:
            emoji = "✅" if g.passed else "❌"
            lines.append(f"  {emoji} {g.name}: {g.detail}")

        await message.answer("\n".join(lines), parse_mode="HTML")

    @dp.message(Command("logs"))
    async def cmd_logs(message: types.Message):
        args = message.text.split()[1:] if message.text else []
        report_type = args[0] if args else "financial_daily"

        runs = state._sb.table("report_runs").select(
            "report_date,status,attempt,confidence,duration_sec,error"
        ).eq("report_type", report_type).order(
            "created_at", desc=True
        ).limit(5).execute().data

        if not runs:
            await message.answer(f"Нет запусков для {report_type}")
            return

        lines = [f"📋 <b>Последние runs: {report_type}</b>\n"]
        for r in runs:
            status_emoji = {"success": "✅", "failed": "❌", "error": "💥"}.get(r["status"], "🔄")
            dur = f"{r.get('duration_sec', 0):.0f}s" if r.get("duration_sec") else "?"
            conf = f"{r.get('confidence', 0):.0%}" if r.get("confidence") else "?"
            lines.append(f"{status_emoji} {r['report_date']} | {r['status']} | {dur} | conf={conf}")

        await message.answer("\n".join(lines), parse_mode="HTML")

    # Callback for playbook review
    @dp.callback_query(lambda c: c.data and c.data.startswith("rule:"))
    async def on_rule_review(callback: types.CallbackQuery):
        _, action, rule_id = callback.data.split(":")
        if action == "approve":
            state.update_rule_status(rule_id, "active")
            await callback.answer("✅ Правило активировано")
        elif action == "reject":
            state.update_rule_status(rule_id, "rejected")
            await callback.answer("❌ Правило отклонено")
        await callback.message.edit_reply_markup(reply_markup=None)
