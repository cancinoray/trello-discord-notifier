#!/usr/bin/env python3
"""
Trello -> Telegram deadline notifier.

Sends a Telegram message for each Trello card with a due date at three
checkpoints:
  - 1 day before, at 08:00 local time
  - Same day, at 08:00 local time (skipped if the deadline itself is before 8am)
  - 30 minutes before the due time

Meant to run every ~15 minutes via GitHub Actions (see .github/workflows/notify.yml).
Already-sent reminders are tracked in state.json so nothing gets repeated.
"""

import os
import json
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

import requests

# ---------- Config ----------
TIMEZONE = os.environ.get("TZ_NAME", "Asia/Manila")
MORNING_HOUR = 8                 # 8 AM local time
WINDOW_MINUTES = 20              # how long a checkpoint stays "firable" after it passes
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

TRELLO_KEY = os.environ["TRELLO_KEY"]
TRELLO_TOKEN = os.environ["TRELLO_TOKEN"]
TRELLO_BOARD_ID = os.environ["TRELLO_BOARD_ID"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TZ = ZoneInfo(TIMEZONE)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_due_cards():
    url = f"https://api.trello.com/1/boards/{TRELLO_BOARD_ID}/cards"
    params = {
        "key": TRELLO_KEY,
        "token": TRELLO_TOKEN,
        "filter": "open",
        "fields": "name,due,dueComplete,shortUrl",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return [c for c in resp.json() if c.get("due") and not c.get("dueComplete")]


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=15,
    )
    resp.raise_for_status()


def checkpoints_for_due(due_local):
    """Return dict of checkpoint_key -> datetime for a given due datetime."""
    due_date = due_local.date()
    day_before = datetime.combine(due_date - timedelta(days=1), dtime(MORNING_HOUR, 0), TZ)
    same_day = datetime.combine(due_date, dtime(MORNING_HOUR, 0), TZ)
    thirty_before = due_local - timedelta(minutes=30)

    cps = {"day_before_8am": day_before}
    # Only fire the "today" 8am reminder if the deadline is actually after 8am
    if due_local.time() > dtime(MORNING_HOUR, 0):
        cps["same_day_8am"] = same_day
    cps["30min_before"] = thirty_before
    return cps


LABELS = {
    "day_before_8am": "Due tomorrow",
    "same_day_8am": "Due today",
    "30min_before": "Due in 30 minutes",
}


def main():
    now = datetime.now(TZ)
    state = load_state()
    cards = fetch_due_cards()
    current_ids = {c["id"] for c in cards}
    sent = 0

    for card in cards:
        card_id = card["id"]
        due_local = datetime.fromisoformat(card["due"].replace("Z", "+00:00")).astimezone(TZ)
        card_state = state.setdefault(card_id, {})

        for key, cp_time in checkpoints_for_due(due_local).items():
            already_sent = card_state.get(key, False)
            in_window = cp_time <= now < cp_time + timedelta(minutes=WINDOW_MINUTES)
            if in_window and not already_sent:
                text = (
                    f"⏰ <b>{LABELS[key]}</b>\n"
                    f"{card['name']}\n"
                    f"Due: {due_local.strftime('%b %d, %I:%M %p')}\n"
                    f"{card['shortUrl']}"
                )
                send_telegram(text)
                card_state[key] = True
                sent += 1

    # Drop state for cards that are no longer open/due (completed, deleted, etc.)
    for cid in list(state.keys()):
        if cid not in current_ids:
            del state[cid]

    save_state(state)
    print(f"Checked {len(cards)} card(s) with due dates, sent {sent} notification(s).")


if __name__ == "__main__":
    main()
