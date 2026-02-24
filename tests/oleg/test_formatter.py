"""Tests for bot formatter."""
from agents.oleg.bot.formatter import (
    split_html_message, add_caveats_header, format_cost_footer,
)


def test_split_short_message():
    text = "Short message"
    chunks = split_html_message(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_long_message():
    # Create a message longer than 4000 chars
    text = "Paragraph one.\n\n" * 300  # ~4800 chars
    chunks = split_html_message(text, max_length=4000)
    assert len(chunks) >= 2
    # All chunks should be within limit
    for chunk in chunks:
        assert len(chunk) <= 4000


def test_split_respects_paragraph_boundaries():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = split_html_message(text, max_length=30)
    assert len(chunks) >= 2
    # Chunks should not split mid-paragraph
    assert "First paragraph." in chunks[0]


def test_add_caveats_header_empty():
    text = "Report text"
    result = add_caveats_header(text, [])
    assert result == text


def test_add_caveats_header_with_caveats():
    text = "Report text"
    result = add_caveats_header(text, ["Low margin fill", "Revenue anomaly"])
    assert "Предупреждения" in result
    assert "Low margin fill" in result
    assert "Revenue anomaly" in result
    assert result.endswith("Report text")


def test_format_cost_footer():
    footer = format_cost_footer(0.0123, 3, 5000)
    assert "$0.0123" in footer
    assert "3" in footer
    assert "5.0" in footer
