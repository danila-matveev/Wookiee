"""
PDF parser — extracts text page by page using pymupdf.

Detects image-heavy PDFs (avg text < 100 chars/page) and skips them.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import fitz  # pymupdf

logger = logging.getLogger(__name__)

# Threshold: if average text per page is below this, consider image-heavy
IMAGE_HEAVY_THRESHOLD = 100  # chars per page


@dataclass
class ParsedSection:
    text: str
    heading: str = ""


def is_image_heavy(file_path: Path) -> bool:
    """Check if a PDF is image-heavy (low text content)."""
    try:
        doc = fitz.open(str(file_path))
        if len(doc) < 3:
            doc.close()
            return False

        total_chars = 0
        for page in doc:
            total_chars += len(page.get_text().strip())

        avg_chars = total_chars / max(len(doc), 1)
        doc.close()

        if avg_chars < IMAGE_HEAVY_THRESHOLD:
            logger.warning(
                "Image-heavy PDF detected: %s (avg %.0f chars/page)",
                file_path.name, avg_chars,
            )
            return True
        return False
    except Exception as e:
        logger.error("Failed to check PDF %s: %s", file_path.name, e)
        return True  # Assume image-heavy on error


def parse_pdf(file_path: Path) -> list[ParsedSection]:
    """
    Parse a PDF file into sections (one per page or group of pages).

    Skips image-heavy PDFs (returns empty list with warning).
    """
    if is_image_heavy(file_path):
        logger.warning("Skipping image-heavy PDF: %s", file_path.name)
        return []

    try:
        doc = fitz.open(str(file_path))
    except Exception as e:
        logger.error("Failed to open PDF %s: %s", file_path.name, e)
        return []

    sections: list[ParsedSection] = []
    current_text_parts: list[str] = []

    for page_num, page in enumerate(doc):
        text = page.get_text().strip()
        if not text:
            continue

        current_text_parts.append(text)

        # Group every 3 pages into a section (for context coherence)
        if len(current_text_parts) >= 3:
            combined = "\n\n".join(current_text_parts)
            sections.append(ParsedSection(
                text=combined,
                heading=f"Стр. {page_num - len(current_text_parts) + 2}-{page_num + 1}",
            ))
            current_text_parts = []

    # Remaining pages
    if current_text_parts:
        combined = "\n\n".join(current_text_parts)
        sections.append(ParsedSection(
            text=combined,
            heading=f"Стр. {doc.page_count - len(current_text_parts) + 1}-{doc.page_count}",
        ))

    doc.close()

    total_chars = sum(len(s.text) for s in sections)
    logger.info(
        "Parsed PDF %s: %d sections, %d chars, %d pages",
        file_path.name, len(sections), total_chars, doc.page_count if hasattr(doc, 'page_count') else 0,
    )
    return sections
