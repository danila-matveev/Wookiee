import platform
import subprocess
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from services.telemost_recorder.config import BROWSER_FLAGS


def _start_xvfb() -> Optional[subprocess.Popen]:
    """Start virtual display on Linux. Returns process handle or None on macOS/Windows."""
    if platform.system() != "Linux":
        return None
    proc = subprocess.Popen(
        ["Xvfb", ":99", "-screen", "0", "1280x720x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


@asynccontextmanager
async def launch_browser() -> AsyncIterator[tuple[Browser, BrowserContext, Page]]:
    """
    Async context manager: launches Chromium headful (Xvfb on Linux) with fake
    media devices. Yields (browser, context, page). Cleans up on exit.

    Usage:
        async with launch_browser() as (browser, context, page):
            await page.goto(url)
    """
    xvfb = _start_xvfb()
    env = {"DISPLAY": ":99"} if platform.system() == "Linux" else {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            env=env,
            args=BROWSER_FLAGS,
        )
        context = await browser.new_context()
        page = await context.new_page()
        try:
            yield browser, context, page
        finally:
            await context.close()
            await browser.close()

    if xvfb is not None:
        xvfb.terminate()
        xvfb.wait()
