"""
Markdown to Notion block conversion.

Shared between sync (notion_sync.py) and async (NotionService) callers.
Pure functions with no dependencies except ``re``.
"""
import re


def _plain(content: str) -> dict:
    return {"type": "text", "text": {"content": content}}


def _annotated(content: str, **annotations) -> dict:
    ann = {"bold": False, "italic": False, "strikethrough": False,
           "underline": False, "code": False, "color": "default"}
    ann.update(annotations)
    return {"type": "text", "text": {"content": content}, "annotations": ann}


def _link(text: str, url: str) -> dict:
    return {"type": "text", "text": {"content": text, "link": {"url": url}}}


# Token pattern: bold, italic, inline code, links, or plain text
_INLINE_RE = re.compile(
    r'(\*\*[^*]+\*\*)'        # **bold**
    r'|(\*[^*]+\*)'           # *italic*
    r'|(`[^`]+`)'             # `code`
    r'|(\[[^\]]+\]\([^)]+\))' # [text](url)
)


def parse_inline(text):
    """Parse inline markdown (bold, italic, code, links, BBCode) into Notion rich_text array."""
    # Normalize BBCode to markdown bold
    text = re.sub(r'\[b\](.*?)\[/b\]', r'**\1**', text)

    parts = []
    last_end = 0

    for m in _INLINE_RE.finditer(text):
        # Append plain text before this match
        if m.start() > last_end:
            parts.append(_plain(text[last_end:m.start()]))

        token = m.group()
        if token.startswith('**') and token.endswith('**'):
            parts.append(_annotated(token[2:-2], bold=True))
        elif token.startswith('`') and token.endswith('`'):
            parts.append(_annotated(token[1:-1], code=True))
        elif token.startswith('['):
            # [text](url)
            link_m = re.match(r'\[([^\]]+)\]\(([^)]+)\)', token)
            if link_m:
                parts.append(_link(link_m.group(1), link_m.group(2)))
        elif token.startswith('*') and token.endswith('*'):
            parts.append(_annotated(token[1:-1], italic=True))

        last_end = m.end()

    # Append remaining plain text
    if last_end < len(text):
        parts.append(_plain(text[last_end:]))

    return parts if parts else [_plain(text)]


def remove_empty_sections(md_text: str) -> str:
    """Remove headers that have no content before the next header of same or higher level."""
    lines = md_text.split('\n')
    parsed = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            parsed.append({'type': 'empty', 'text': line})
            continue

        match = re.match(r'^(#+)\s+(.+)', stripped)
        if match:
            level = len(match.group(1))
            parsed.append({'type': 'header', 'level': level, 'text': line})
        else:
            parsed.append({'type': 'content', 'text': line})

    indices_to_remove = set()

    for i in range(len(parsed)):
        item = parsed[i]
        if item['type'] == 'header':
            has_content = False
            for j in range(i + 1, len(parsed)):
                next_item = parsed[j]
                if next_item['type'] == 'content':
                    has_content = True
                    break
                if next_item['type'] == 'header':
                    if next_item['level'] <= item['level']:
                        break

            if not has_content:
                indices_to_remove.add(i)
                # Also remove trailing empty lines between removed header and next
                for k in range(i + 1, len(parsed)):
                    if parsed[k]['type'] == 'empty':
                        indices_to_remove.add(k)
                    else:
                        break

    result_lines = []
    for i in range(len(parsed)):
        if i not in indices_to_remove:
            result_lines.append(parsed[i]['text'])

    return '\n'.join(result_lines)


def md_to_notion_blocks(md_text: str) -> list:
    """Convert Markdown report to Notion block array.

    Handles headings, tables (with 100-row chunking), code blocks,
    bullet/numbered lists, dividers, and paragraphs.
    """
    blocks = []
    lines = md_text.split('\n')
    i = 0
    table_rows = []
    in_table = False
    in_code_block = False
    code_content = []

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        num_cols = max(len(r) for r in table_rows)
        notion_rows = []
        for row in table_rows:
            while len(row) < num_cols:
                row.append('')
            cells_rt = [
                parse_inline(cell[:2000])
                for cell in row[:num_cols]
            ]
            notion_rows.append({
                "object": "block",
                "type": "table_row",
                "table_row": {"cells": cells_rt},
            })
        # Notion API limits tables to 100 rows.
        # Split: first chunk = 100 rows (incl. header),
        # remaining chunks = header copy + 99 data rows = 100.
        MAX_ROWS = 100
        header_row = notion_rows[0] if notion_rows else None
        first_chunk = notion_rows[:MAX_ROWS]
        blocks.append({
            "object": "block",
            "type": "table",
            "table": {
                "table_width": num_cols,
                "has_column_header": True,
                "has_row_header": False,
                "children": first_chunk,
            },
        })
        remaining = notion_rows[MAX_ROWS:]
        while remaining:
            chunk = remaining[:MAX_ROWS - 1]
            remaining = remaining[MAX_ROWS - 1:]
            if header_row:
                chunk = [header_row] + chunk
            blocks.append({
                "object": "block",
                "type": "table",
                "table": {
                    "table_width": num_cols,
                    "has_column_header": True,
                    "has_row_header": False,
                    "children": chunk,
                },
            })
        table_rows = []

    while i < len(lines):
        line = lines[i]

        # Code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": '\n'.join(code_content)[:2000]}}],
                        "language": "plain text",
                    },
                })
                code_content = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_content.append(line)
            i += 1
            continue

        # Tables
        if '|' in line and line.strip().startswith('|'):
            stripped = line.strip()
            if re.match(r'^[\|\-\s:]+$', stripped):
                i += 1
                continue
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(cells)

            next_is_table = (
                i + 1 < len(lines)
                and lines[i + 1].strip().startswith('|')
                and '|' in lines[i + 1]
            )
            if not next_is_table:
                flush_table()
                in_table = False
            i += 1
            continue

        # Headings (generic regex handles any level, capped at heading_3)
        header_match = re.match(r'^(#+)\s+(.+)', line.strip())
        if header_match:
            level = len(header_match.group(1))
            content = header_match.group(2).strip()
            notion_level = min(level, 3)
            block_type = f"heading_{notion_level}"

            # Toggle heading: ▶ marker means collapsible section
            if content.startswith('\u25b6'):
                toggle_content = content.lstrip('\u25b6').strip()
                # Collect child lines until next heading of same or higher level
                child_lines = []
                i += 1
                while i < len(lines):
                    child_line = lines[i]
                    child_header = re.match(r'^(#+)\s+', child_line.strip())
                    if child_header and len(child_header.group(1)) <= level:
                        break
                    child_lines.append(child_line)
                    i += 1

                # Recursively parse children
                children = md_to_notion_blocks('\n'.join(child_lines))

                blocks.append({
                    "object": "block",
                    "type": block_type,
                    block_type: {
                        "rich_text": parse_inline(toggle_content[:2000]),
                        "is_toggleable": True,
                        "children": children if children else [],
                    },
                })
                # i already points to next section; don't increment
                continue

            blocks.append({
                "object": "block",
                "type": block_type,
                block_type: {
                    "rich_text": [{"type": "text", "text": {"content": content[:2000]}}]
                },
            })
            i += 1
            continue

        # Callout: > [icon] text  OR  > ⚠️ text  OR  > 💡 text
        callout_match = re.match(r'^>\s*([^\s])\s+(.+)', line.strip())
        if callout_match:
            icon = callout_match.group(1)
            callout_text = callout_match.group(2)
            # Collect continuation lines (> text)
            i += 1
            while i < len(lines) and lines[i].strip().startswith('>'):
                cont = lines[i].strip()
                cont = re.sub(r'^>\s*', '', cont)
                callout_text += '\n' + cont
                i += 1
            # Map common icons to colors
            color_map = {'⚠️': 'yellow_background', '❌': 'red_background',
                         '✅': 'green_background', '💡': 'green_background',
                         '🔥': 'green_background', '📊': 'blue_background',
                         '🎯': 'green_background', '📉': 'green_background',
                         '🚀': 'purple_background', '📱': 'yellow_background'}
            color = color_map.get(icon, 'gray_background')
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": parse_inline(callout_text),
                    "icon": {"type": "emoji", "emoji": icon},
                    "color": color,
                },
            })
            continue

        # Divider
        if line.strip() == '---':
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue

        # Bullet list
        if line.strip().startswith('- '):
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": parse_inline(line.strip()[2:])},
            })
            i += 1
            continue

        # Numbered list
        if re.match(r'^\d+\.\s', line.strip()):
            text = re.sub(r'^\d+\.\s*', '', line.strip())
            blocks.append({
                "object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": parse_inline(text)},
            })
            i += 1
            continue

        # Empty line
        if line.strip() == '':
            i += 1
            continue

        # Paragraph
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": parse_inline(line)},
        })
        i += 1

    return blocks
