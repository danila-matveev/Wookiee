"""
JSON extraction utilities for LLM responses.

LLMs often wrap JSON in markdown code blocks (```json ... ```)
or include extra text around JSON. These utilities handle extraction.
"""
import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def extract_json(text: str) -> Optional[dict]:
    """
    Extract JSON dict from LLM response text with multiple fallback strategies.

    Strategy chain:
    1. Direct json.loads() — clean JSON response
    2. Strip markdown code fences (```json ... ``` or ``` ... ```)
    3. Find JSON object substring using brace matching

    Returns:
        Parsed dict or None if extraction fails.
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Strategy 1: Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip markdown code fences (greedy match for multiline JSON)
    md_match = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n\s*```', text)
    if md_match:
        try:
            result = json.loads(md_match.group(1).strip())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    # Strategy 2b: Fallback for single-line or no-newline fences
    if '```' in text:
        md_match2 = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        if md_match2:
            try:
                result = json.loads(md_match2.group(1).strip())
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

    # Strategy 3: Find first JSON object by matching braces
    first_brace = text.find('{')
    if first_brace != -1:
        depth = 0
        in_string = False
        escape_next = False
        for i in range(first_brace, len(text)):
            ch = text[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[first_brace:i + 1]
                    try:
                        result = json.loads(candidate)
                        if isinstance(result, dict):
                            return result
                    except json.JSONDecodeError:
                        pass
                    break

    # Strategy 4: Truncated JSON repair — try closing open strings/braces
    if first_brace is not None and first_brace != -1:
        candidate = text[first_brace:]
        # Try progressively closing the JSON
        for suffix in ['"}', '"}}', '"}}}', '"}]}}']:
            try:
                result = json.loads(candidate + suffix)
                if isinstance(result, dict):
                    logger.info("extract_json: repaired truncated JSON")
                    return result
            except json.JSONDecodeError:
                continue

    return None
