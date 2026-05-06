#!/usr/bin/env python3
"""Fetch tasks and chat messages from Bitrix24 for analytics report."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from config import STAFF, EXCLUDED_IDS, CEO_ID

API_BASE = os.environ.get("Bitrix_rest_api", "").rstrip("/")
TIMEOUT = 30


def log(msg):
    print(msg, file=sys.stderr)


def api_call(method, params=None):
    """Call Bitrix24 REST API method with JSON response."""
    url = f"{API_BASE}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as e:
        log(f"  API error ({method}): {e}")
        return None


def fetch_tasks(start_date):
    """Fetch tasks changed since start_date with pagination."""
    all_tasks = []
    start = 0
    date_str = start_date.strftime("%Y-%m-%dT00:00:00")

    while True:
        log(f"  Fetching tasks (offset {start})...")
        params = {
            "filter[>=CHANGED_DATE]": date_str,
            "select[]": [
                "ID", "TITLE", "STATUS", "RESPONSIBLE_ID", "CREATED_BY",
                "GROUP_ID", "DEADLINE", "CLOSED_DATE", "CHANGED_DATE",
                "CREATED_DATE", "PRIORITY", "TAGS", "DESCRIPTION",
            ],
            "start": start,
        }
        data = api_call("tasks.task.list", params)
        if not data or "result" not in data:
            break

        tasks = data["result"].get("tasks", [])
        all_tasks.extend(tasks)

        total = int(data.get("total", 0))
        start += 50
        if start >= total:
            break

    log(f"  Total tasks fetched: {len(all_tasks)}")
    return all_tasks


def fetch_recent_chats():
    """Fetch list of recent chats."""
    log("  Fetching recent chats...")
    data = api_call("im.recent.get", {"LIMIT": 200})
    if not data or "result" not in data:
        return []
    result = data["result"]
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return result.get("items", list(result.values()))
    return []


def fetch_chat_messages(chat_id, limit=30):
    """Fetch recent messages from a specific chat."""
    data = api_call("im.dialog.messages.get", {
        "DIALOG_ID": f"chat{chat_id}",
        "LIMIT": limit,
    })
    if not data or "result" not in data:
        return []
    messages = data["result"].get("messages", [])
    if isinstance(messages, dict):
        messages = list(messages.values())
    return messages


def resolve_author_name(author_id):
    """Resolve author ID to name from STAFF config."""
    author_id = int(author_id) if author_id else 0
    if author_id in STAFF:
        return STAFF[author_id]["name"]
    return f"ID:{author_id}"


def fetch_calendar_events(user_id, start_date, end_date):
    """Fetch calendar events for a specific user in date range."""
    params = {
        "type": "user",
        "ownerId": user_id,
        "from": start_date.strftime("%Y-%m-%dT00:00:00"),
        "to": end_date.strftime("%Y-%m-%dT23:59:59"),
    }
    data = api_call("calendar.event.get", params)
    if not data or "result" not in data:
        return []
    result = data["result"]
    if not isinstance(result, list):
        return []
    # Normalize events
    events = []
    for ev in result:
        codes = ev.get("ATTENDEES_CODES") or []
        attendee_ids = []
        for c in codes:
            if isinstance(c, str) and c.startswith("U"):
                try:
                    attendee_ids.append(int(c[1:]))
                except ValueError:
                    pass
        events.append({
            "name": ev.get("NAME", ""),
            "date_from": ev.get("DATE_FROM", ""),
            "date_to": ev.get("DATE_TO", ""),
            "description": ev.get("DESCRIPTION", "") or "",
            "attendee_ids": attendee_ids,
            "attendee_names": [resolve_author_name(aid) for aid in attendee_ids],
        })
    return events


def fetch_ceo_dm(peer_user_id, start_date, days):
    """Fetch 1:1 messages between CEO and a specific user, within date range.
    Uses pagination via LAST_ID. Assumes webhook is authenticated as CEO.
    """
    cutoff = start_date.strftime("%Y-%m-%dT00:00:00")
    all_msgs = []
    last_id = None
    # Safety limit — 10 pages * 100 msgs = 1000 msgs per dialog is plenty for 7 days
    for _ in range(10):
        params = {"DIALOG_ID": peer_user_id, "LIMIT": 100}
        if last_id:
            params["LAST_ID"] = last_id
        data = api_call("im.dialog.messages.get", params)
        if not data or "result" not in data:
            break
        result = data["result"]
        if not isinstance(result, dict):
            break
        msgs = result.get("messages", [])
        if not msgs:
            break
        all_msgs.extend(msgs)
        oldest = msgs[-1]
        oldest_date = oldest.get("date", "")
        if isinstance(oldest_date, str) and oldest_date < cutoff:
            break
        last_id = oldest.get("id")
        if not last_id:
            break
    # Filter to cutoff, normalize
    filtered = []
    for m in all_msgs:
        md = m.get("date", "")
        if isinstance(md, str) and md >= cutoff:
            filtered.append({
                "author_id": int(m.get("author_id", 0)),
                "author_name": resolve_author_name(m.get("author_id", 0)),
                "date": md,
                "text": m.get("text", ""),
            })
    filtered.sort(key=lambda x: x["date"])
    return filtered


def main():
    parser = argparse.ArgumentParser(description="Fetch Bitrix24 data for analytics")
    parser.add_argument("--days", type=int, default=7, help="Period in days (default: 7)")
    parser.add_argument("--output", default="/tmp/bitrix_report_data.json", help="Output JSON path")
    args = parser.parse_args()

    if not API_BASE:
        log("ERROR: Bitrix_rest_api not found in .env")
        sys.exit(1)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)

    log(f"Period: {start_date.strftime('%Y-%m-%d')} — {end_date.strftime('%Y-%m-%d')}")

    # 1. Fetch tasks
    log("Fetching tasks...")
    tasks = fetch_tasks(start_date)

    # Enrich tasks with staff names
    for task in tasks:
        resp_id = int(task.get("responsibleId", task.get("RESPONSIBLE_ID", 0)))
        creator_id = int(task.get("createdBy", task.get("CREATED_BY", 0)))
        task["_responsible_name"] = resolve_author_name(resp_id)
        task["_creator_name"] = resolve_author_name(creator_id)

    # 2. Fetch recent chats
    log("Fetching chats...")
    recent_chats = fetch_recent_chats()

    # Filter: only group chats with activity in period
    start_str = start_date.strftime("%Y-%m-%dT00:00:00")
    active_chats = []
    for chat in recent_chats:
        chat_type = chat.get("type", "")
        if chat_type != "chat":
            continue
        # Check activity date
        last_activity = chat.get("date_last_activity", chat.get("message", {}).get("date", ""))
        if isinstance(last_activity, str) and last_activity >= start_str:
            active_chats.append(chat)

    log(f"  Active group chats in period: {len(active_chats)}")

    # Sort by activity, take top 40
    active_chats = active_chats[:40]

    # 3. Fetch messages from active chats
    log("Fetching chat messages...")
    chats_data = {}
    for i, chat in enumerate(active_chats):
        chat_id = chat.get("chat_id", chat.get("id", ""))
        chat_title = chat.get("title", chat.get("chat", {}).get("title", f"Chat {chat_id}"))

        if not chat_id:
            continue

        log(f"  [{i+1}/{len(active_chats)}] {chat_title}...")
        messages = fetch_chat_messages(chat_id)

        # Filter messages: only in period, exclude system (author_id=0)
        filtered = []
        for msg in messages:
            author_id = int(msg.get("author_id", 0))
            if author_id == 0:
                continue
            msg_date = msg.get("date", "")
            if isinstance(msg_date, str) and msg_date >= start_str:
                filtered.append({
                    "author_id": author_id,
                    "author_name": resolve_author_name(author_id),
                    "date": msg_date,
                    "text": msg.get("text", ""),
                })

        if filtered:
            chats_data[str(chat_id)] = {
                "name": chat_title,
                "messages": filtered,
            }

    log(f"  Chats with messages: {len(chats_data)}")

    # 4. Fetch calendar events for each staff member
    log("Fetching calendar events per staff...")
    calendar_data = {}
    for uid, info in STAFF.items():
        events = fetch_calendar_events(uid, start_date, end_date)
        calendar_data[str(uid)] = events
        log(f"  {info['name']}: {len(events)} events")

    # 5. Fetch CEO 1:1 dialogs with each staff member (excluding CEO itself)
    log("Fetching CEO 1:1 dialogs...")
    ceo_dms = {}
    for uid, info in STAFF.items():
        if uid == CEO_ID:
            continue
        msgs = fetch_ceo_dm(uid, start_date, args.days)
        if msgs:
            ceo_dms[str(uid)] = {"peer_name": info["name"], "messages": msgs}
            log(f"  Данила ↔ {info['name']}: {len(msgs)} messages")

    # 6. Save result
    result = {
        "tasks": tasks,
        "chats": chats_data,
        "calendar": calendar_data,
        "ceo_dms": ceo_dms,
        "period": {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "days": args.days,
        },
        "staff": {str(k): v for k, v in STAFF.items()},
        "ceo_id": CEO_ID,
        "excluded_ids": list(EXCLUDED_IDS),
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log(f"Data saved to {args.output}")
    total_cal = sum(len(v) for v in calendar_data.values())
    total_dm = sum(len(v["messages"]) for v in ceo_dms.values())
    log(f"Tasks: {len(tasks)} | Chats: {len(chats_data)} | Calendar: {total_cal} events | CEO DMs: {total_dm} msgs across {len(ceo_dms)} dialogs")


if __name__ == "__main__":
    main()
