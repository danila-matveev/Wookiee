import json
import os
import urllib.request
from datetime import UTC, datetime

import yaml

from services.telemost_recorder.config import BITRIX_REST_API, SPEAKERS_FILE
from services.telemost_recorder.transcribe import TranscriptSegment

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# MAIN tier per economics rules: analytics, tool-use
_LLM_MODEL = "google/gemini-3-flash-preview"


def sync_from_bitrix() -> list[dict]:
    """Fetch active users from Bitrix24 REST API webhook."""
    employees = []
    start = 0
    while True:
        url = f"{BITRIX_REST_API}user.get?ACTIVE=Y&start={start}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
        for user in data.get("result", []):
            name = f"{user.get('NAME', '')} {user.get('LAST_NAME', '')}".strip()
            employees.append({
                "bitrix_id": str(user["ID"]),
                "name": name,
                "short_name": user.get("NAME", name),
            })
        if data.get("next"):
            start = data["next"]
        else:
            break
    return employees


def load_speakers() -> list[dict]:
    """Load speakers.yml. Returns empty list if file missing."""
    if not SPEAKERS_FILE.exists():
        return []
    with open(SPEAKERS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("employees", [])


def save_speakers(employees: list[dict]) -> None:
    """Write employees list to speakers.yml."""
    SPEAKERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEAKERS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(
            {"updated_at": datetime.now(UTC).isoformat(), "employees": employees},
            f,
            allow_unicode=True,
            default_flow_style=False,
        )


def resolve_speakers(
    segments: list[TranscriptSegment],
    participants: list[str],
    employees: list[dict],
) -> dict[str, str]:
    """Map Speaker N labels to real names via LLM. Returns {Speaker N: name}."""
    if not segments or not participants:
        return {}

    speaker_labels = sorted({s.speaker for s in segments})
    from services.telemost_recorder.config import KNOWN_BOT_NAMES  # local import to avoid circular
    participant_names = [p for p in participants if p.lower() not in KNOWN_BOT_NAMES]
    if not participant_names:
        return {}

    # Filter roster to only participants who were in this meeting (by name match)
    roster_names = {e["name"] for e in employees}
    known = [n for n in participant_names if n in roster_names]
    # Fall back to all participant names if none matched the roster
    resolved_participants = known if known else participant_names

    excerpt = "\n".join(f"[{s.speaker}]: {s.text}" for s in segments[:60])

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        print("WARNING: OPENROUTER_API_KEY not set, skipping speaker resolution")
        return {}

    payload = json.dumps({
        "model": _LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Meeting participants: {resolved_participants}\n"
                    f"Speaker labels in transcript: {speaker_labels}\n\n"
                    f"Transcript excerpt:\n{excerpt}\n\n"
                    "Map each speaker label to a participant name based on context clues "
                    "(names mentioned, topics, greeting phrases). "
                    'Return ONLY valid JSON like: {"Speaker 1": "Full Name", "Speaker 2": "Full Name"}. '
                    "If you cannot confidently match a speaker, keep the original label."
                ),
            }
        ],
        "max_tokens": 300,
    }).encode()

    req = urllib.request.Request(_OPENROUTER_URL, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {openrouter_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        content = result["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
        if "```" in content:
            inner = content.split("```")
            # Take the first non-empty fenced block
            for block in inner[1::2]:
                block = block.lstrip("json").strip()
                if block:
                    content = block
                    break
        # Find JSON object even if LLM wraps it in prose
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end != -1:
            content = content[start:end + 1]
        mapping = json.loads(content)
        return {k: v for k, v in mapping.items() if k in speaker_labels}
    except Exception as exc:
        print(f"WARNING: speaker resolution failed: {exc}")
        return {}
