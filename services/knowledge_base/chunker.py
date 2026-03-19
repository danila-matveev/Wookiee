"""
Text chunker — splits parsed sections into embedding-sized chunks.

Recursive character splitting with context headers for retrieval quality.
"""

import re
from dataclasses import dataclass
from typing import Optional

from . import config


@dataclass
class TextChunk:
    text: str
    chunk_index: int
    metadata: dict


def chunk_text(
    text: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> list[str]:
    """
    Split text into overlapping chunks using recursive separators.

    Split hierarchy: double newline → single newline → sentence boundary → space.
    """
    chunk_size = chunk_size or config.CHUNK_SIZE
    chunk_overlap = chunk_overlap or config.CHUNK_OVERLAP

    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    separators = ["\n\n", "\n", ". ", " "]
    return _recursive_split(text, separators, chunk_size, chunk_overlap)


def _recursive_split(
    text: str,
    separators: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Recursively split text using the first separator that produces chunks."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    # Try each separator
    for sep in separators:
        parts = text.split(sep)
        if len(parts) <= 1:
            continue

        chunks = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part

            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())
                # If single part exceeds chunk_size, try next separator
                if len(part) > chunk_size:
                    remaining_seps = separators[separators.index(sep) + 1:]
                    if remaining_seps:
                        sub_chunks = _recursive_split(
                            part, remaining_seps, chunk_size, chunk_overlap
                        )
                        chunks.extend(sub_chunks)
                        current = ""
                    else:
                        # Last resort: hard split
                        for i in range(0, len(part), chunk_size - chunk_overlap):
                            chunks.append(part[i:i + chunk_size].strip())
                        current = ""
                else:
                    current = part

        if current.strip():
            chunks.append(current.strip())

        if chunks:
            # Add overlap between chunks
            return _add_overlap(chunks, chunk_overlap)

    # Fallback: hard split by character count
    chunks = []
    for i in range(0, len(text), chunk_size - chunk_overlap):
        chunk = text[i:i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _add_overlap(chunks: list[str], overlap: int) -> list[str]:
    """Add overlap from the end of previous chunk to the start of next."""
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        # Take last `overlap` chars from previous chunk
        overlap_text = prev[-overlap:] if len(prev) > overlap else prev
        # Find a clean break point (start of word/sentence)
        space_idx = overlap_text.find(" ")
        if space_idx > 0:
            overlap_text = overlap_text[space_idx + 1:]
        result.append(overlap_text + " " + chunks[i])

    return result


def chunk_sections(
    sections: list,
    module: str,
    file_name: str,
    file_type: str,
    content_type: str,
    is_cleaned: bool = False,
    source_path: str = "",
) -> list[TextChunk]:
    """
    Chunk parsed sections into TextChunks with metadata and context headers.

    Each chunk gets a context header: [Модуль N] [file_name]
    """
    all_chunks = []
    chunk_index = 0

    for section in sections:
        text = section.text.strip()
        if not text:
            continue

        # Add context header for better retrieval
        header = f"[Модуль {module}] [{file_name}]"
        if section.heading:
            header += f" — {section.heading}"

        raw_chunks = chunk_text(text)

        for raw in raw_chunks:
            # Prepend header to each chunk
            chunk_text_with_header = f"{header}\n\n{raw}"

            all_chunks.append(TextChunk(
                text=chunk_text_with_header,
                chunk_index=chunk_index,
                metadata={
                    "module": module,
                    "file_name": file_name,
                    "file_type": file_type,
                    "content_type": content_type,
                    "is_cleaned": is_cleaned,
                    "source_path": source_path,
                },
            ))
            chunk_index += 1

    return all_chunks
