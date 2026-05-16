"""Tests for join.dump_participants_dom — diagnostic DOM capture helper."""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from services.telemost_recorder.join import dump_participants_dom


_PAGE_WITH_PANEL = """
<html>
  <body>
    <div data-testid='meeting-controls'>
      <button data-testid='participants-button'>Участники</button>
    </div>
    <aside data-testid='participants-panel'>
      <div class='participant-name'>Alice</div>
      <div class='participant-name'>Bob</div>
    </aside>
  </body>
</html>
"""


_PAGE_WITHOUT_PARTICIPANTS_BUTTON = """
<html>
  <body>
    <div>No participants button here</div>
  </body>
</html>
"""


@pytest.mark.anyio
async def test_dump_writes_file_with_panel_html(tmp_path: Path) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_PAGE_WITH_PANEL)
        out = await dump_participants_dom(page, tmp_path)
        await browser.close()

    assert out is not None
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    # panel should be captured
    assert "Alice" in content
    assert "Bob" in content
    # full page should also be captured
    assert "<!-- panel -->" in content
    assert "<!-- full-page -->" in content


@pytest.mark.anyio
async def test_dump_writes_file_even_when_no_button(tmp_path: Path) -> None:
    """If the Участники button isn't found, we still want a full-page snapshot
    so the operator can see what state the page was actually in."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_PAGE_WITHOUT_PARTICIPANTS_BUTTON)
        out = await dump_participants_dom(page, tmp_path)
        await browser.close()

    assert out is not None
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "No participants button here" in content
    assert "<!-- full-page -->" in content


@pytest.mark.anyio
async def test_dump_creates_output_dir(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / "dir"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_PAGE_WITHOUT_PARTICIPANTS_BUTTON)
        out = await dump_participants_dom(page, nested)
        await browser.close()

    assert out is not None
    assert nested.is_dir()
    assert out.parent == nested
