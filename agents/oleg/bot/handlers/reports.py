"""
Report handlers — on-demand reports via pipeline.
"""
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from agents.oleg.services.time_utils import (
    get_yesterday_msk, get_last_week_bounds_msk,
)

logger = logging.getLogger(__name__)

router = Router()


async def _save_to_notion(result, request) -> str | None:
    """Save report to Notion, return page URL or None."""
    try:
        from agents.oleg import config
        from agents.oleg.services.notion_service import NotionService
        notion = NotionService(
            token=config.NOTION_TOKEN,
            database_id=config.NOTION_DATABASE_ID,
        )
        if not notion.enabled:
            return None
        return await notion.sync_report(
            start_date=request.start_date if request else "",
            end_date=request.end_date if request else "",
            report_md=result.detailed_report or result.brief_summary,
            report_type=result.report_type.value if hasattr(result, 'report_type') else "Ежедневный фин анализ",
            chain_steps=result.chain_steps,
        )
    except Exception as e:
        logger.warning(f"Notion save failed (non-critical): {e}")
        return None


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Ещё отчёт", callback_data="menu_reports")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")],
        ]
    )


@router.callback_query(F.data == "report_daily")
async def callback_daily_report(callback: CallbackQuery, pipeline=None, bot_instance=None):
    """Generate daily report on demand."""
    await callback.message.edit_text("⏳ Генерирую дневной отчёт...")

    if not pipeline:
        await callback.message.edit_text(
            "❌ Pipeline не настроен.", reply_markup=_back_keyboard()
        )
        return

    from agents.oleg.pipeline.report_types import ReportType, ReportRequest
    yesterday = get_yesterday_msk()
    request = ReportRequest(
        report_type=ReportType.DAILY,
        start_date=str(yesterday),
        end_date=str(yesterday),
    )

    try:
        result = await pipeline.generate_report(request)
        if result:
            from agents.oleg.bot.formatter import (
                split_html_message, format_cost_footer,
            )

            page_url = await _save_to_notion(result, request)

            text = result.brief_summary
            text += format_cost_footer(
                result.cost_usd, result.chain_steps, result.duration_ms,
            )
            if page_url:
                text += f'\n\n<a href="{page_url}">Подробный отчёт в Notion</a>'
            for chunk in split_html_message(text):
                await callback.message.answer(chunk, parse_mode="HTML")
            await callback.message.answer(
                "Отчёт готов!", reply_markup=_back_keyboard()
            )
        else:
            await callback.message.answer(
                "❌ Не удалось сгенерировать отчёт (hard gates failed).",
                reply_markup=_back_keyboard(),
            )
    except Exception as e:
        logger.error(f"Daily report error: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ Ошибка: {e}", reply_markup=_back_keyboard()
        )


@router.callback_query(F.data == "report_weekly")
async def callback_weekly_report(callback: CallbackQuery, pipeline=None, bot_instance=None):
    """Generate weekly report on demand."""
    await callback.message.edit_text("⏳ Генерирую недельный отчёт...")

    if not pipeline:
        await callback.message.edit_text(
            "❌ Pipeline не настроен.", reply_markup=_back_keyboard()
        )
        return

    from agents.oleg.pipeline.report_types import ReportType, ReportRequest
    monday, sunday = get_last_week_bounds_msk()
    request = ReportRequest(
        report_type=ReportType.WEEKLY,
        start_date=str(monday),
        end_date=str(sunday),
    )

    try:
        result = await pipeline.generate_report(request)
        if result:
            from agents.oleg.bot.formatter import (
                split_html_message, format_cost_footer,
            )

            page_url = await _save_to_notion(result, request)

            text = result.brief_summary
            text += format_cost_footer(
                result.cost_usd, result.chain_steps, result.duration_ms,
            )
            if page_url:
                text += f'\n\n<a href="{page_url}">Подробный отчёт в Notion</a>'
            for chunk in split_html_message(text):
                await callback.message.answer(chunk, parse_mode="HTML")
            await callback.message.answer(
                "Отчёт готов!", reply_markup=_back_keyboard()
            )
        else:
            await callback.message.answer(
                "❌ Не удалось сгенерировать отчёт (hard gates failed).",
                reply_markup=_back_keyboard(),
            )
    except Exception as e:
        logger.error(f"Weekly report error: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ Ошибка: {e}", reply_markup=_back_keyboard()
        )
