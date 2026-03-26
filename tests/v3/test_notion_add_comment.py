"""Tests for NotionDelivery.add_comment()."""
import pytest
from unittest.mock import AsyncMock, patch

from shared.notion_client import NotionClient as NotionDelivery


@pytest.mark.asyncio
async def test_add_comment_posts_to_notion_api():
    """add_comment() should POST to /comments endpoint with page_id and text."""
    notion = NotionDelivery(token="test-token", database_id="test-db")

    with patch.object(notion, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"id": "comment-123"}
        await notion.add_comment("page-abc", "Hello from PromptTuner")

    mock_req.assert_called_once_with("POST", "comments", {
        "parent": {"page_id": "page-abc"},
        "rich_text": [{"type": "text", "text": {"content": "Hello from PromptTuner"}}],
    })


@pytest.mark.asyncio
async def test_add_comment_truncates_long_text():
    """Text longer than 2000 chars should be truncated."""
    notion = NotionDelivery(token="test-token", database_id="test-db")
    long_text = "x" * 3000

    with patch.object(notion, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"id": "c-1"}
        await notion.add_comment("page-1", long_text)

    call_args = mock_req.call_args[0]
    posted_text = call_args[2]["rich_text"][0]["text"]["content"]
    assert len(posted_text) == 2000


@pytest.mark.asyncio
async def test_add_comment_noop_when_disabled():
    """add_comment() does nothing if Notion is not configured."""
    notion = NotionDelivery(token="", database_id="")
    with patch.object(notion, "_request", new_callable=AsyncMock) as mock_req:
        await notion.add_comment("page-1", "test")
    mock_req.assert_not_called()


@pytest.mark.asyncio
async def test_add_comment_swallows_api_error():
    """add_comment() logs warning on API error, does not raise."""
    notion = NotionDelivery(token="test-token", database_id="test-db")

    with patch.object(notion, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = Exception("API error")
        # Should not raise
        await notion.add_comment("page-1", "test")
