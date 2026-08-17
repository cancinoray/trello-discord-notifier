#!/usr/bin/env python3
"""
Trello -> Discord deadline notifier.

Sends a Discord message for each Trello card with a due date at three
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

TZ = ZoneInfo(TIMEZONE)

LABELS = {
    "day_before_8am": "Due tomorrow",
    "same_day_8am": "Due today",
    "30min_before": "Due in 30 minutes",
}


class TrelloClient:
    def __init__(self, key, token, board_id):
        self._key = key
        self._token = token
        self._board_id = board_id

    def fetch_due_cards(self):
        url = f"https://api.trello.com/1/boards/{self._board_id}/cards"
        params = {
            "key": self._key,
            "token": self._token,
            "filter": "open",
            "fields": "name,due,dueComplete,shortUrl",
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return [c for c in resp.json() if c.get("due") and not c.get("dueComplete")]

    def fetch_self_member_id(self):
        url = "https://api.trello.com/1/members/me"
        params = {"key": self._key, "token": self._token, "fields": "id"}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()["id"]

    def fetch_actions_since(self, cursor):
        """Return board actions newer than `cursor` (an Action id), oldest first."""
        url = f"https://api.trello.com/1/boards/{self._board_id}/actions"
        params = {
            "key": self._key,
            "token": self._token,
            "filter": "createCard,updateCard,commentCard",
            "limit": 1000,
        }
        if cursor is not None:
            params["since"] = cursor
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return list(reversed(resp.json()))  # Trello returns newest first


class DiscordClient:
    def __init__(self, webhook_url):
        self._webhook_url = webhook_url

    def send(self, text):
        resp = requests.post(
            self._webhook_url,
            json={"content": text},
            timeout=15,
        )
        resp.raise_for_status()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


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


def _process_due_soon(trello, discord, state, now):
    cards = trello.fetch_due_cards()
    current_ids = {c["id"] for c in cards}
    sent = 0
    checkpoints = state.setdefault("cards", {})

    for card in cards:
        card_id = card["id"]
        due_local = datetime.fromisoformat(card["due"].replace("Z", "+00:00")).astimezone(TZ)
        card_state = checkpoints.setdefault(card_id, {})

        for key, cp_time in checkpoints_for_due(due_local).items():
            already_sent = card_state.get(key, False)
            in_window = cp_time <= now < cp_time + timedelta(minutes=WINDOW_MINUTES)
            if in_window and not already_sent:
                text = (
                    f"⏰ **{LABELS[key]}**\n"
                    f"{card['name']}\n"
                    f"Due: {due_local.strftime('%b %d, %I:%M %p')}\n"
                    f"{card['shortUrl']}"
                )
                discord.send(text)
                card_state[key] = True
                sent += 1

    # Drop state for cards that are no longer open/due (completed, deleted, etc.)
    for cid in list(checkpoints.keys()):
        if cid not in current_ids:
            del checkpoints[cid]

    return sent


def _process_logged_events(trello, discord, state, self_member_id, now):
    is_first_run = "action_cursor" not in state
    cursor = state.get("action_cursor")
    actions = trello.fetch_actions_since(cursor)
    sent = 0

    if is_first_run:
        # Seed the cursor without notifying on the board's pre-existing history.
        # Always write a cursor, even with zero actions, so the run no longer
        # looks like "first run" next time and doesn't swallow future actions.
        # Trello's `since` param accepts an ISO 8601 datetime as well as an Action id.
        state["action_cursor"] = actions[-1]["id"] if actions else now.isoformat()
        return sent

    for action in actions:
        if action["memberCreator"]["id"] != self_member_id:
            card = action["data"]["card"]
            if action["type"] == "createCard":
                text = (
                    f"🆕 **Card created**\n"
                    f"{card['name']}\n"
                    f"https://trello.com/c/{card['shortLink']}"
                )
                discord.send(text)
                sent += 1
            elif (
                action["type"] == "updateCard"
                and "listBefore" in action["data"]
                and action["data"]["listBefore"]["id"] != action["data"]["listAfter"]["id"]
            ):
                list_before = action["data"]["listBefore"]["name"]
                list_after = action["data"]["listAfter"]["name"]
                text = (
                    f"➡️ **Card moved**\n"
                    f"{card['name']}\n"
                    f"{list_before} → {list_after}\n"
                    f"https://trello.com/c/{card['shortLink']}"
                )
                discord.send(text)
                sent += 1
            elif action["type"] == "commentCard":
                commenter = action["memberCreator"]["fullName"]
                text = (
                    f"💬 **New comment**\n"
                    f"{card['name']}\n"
                    f"{commenter}: {action['data']['text']}\n"
                    f"https://trello.com/c/{card['shortLink']}"
                )
                discord.send(text)
                sent += 1

    if actions:
        state["action_cursor"] = actions[-1]["id"]

    return sent


def run(trello, discord, state, now=None):
    """Orchestrate a single check: due-soon reminders plus board-activity notifications."""
    if now is None:
        now = datetime.now(TZ)

    self_member_id = trello.fetch_self_member_id()
    state["self_member_id"] = self_member_id

    sent = _process_due_soon(trello, discord, state, now)
    sent += _process_logged_events(trello, discord, state, self_member_id, now)

    return sent


def main():
    trello = TrelloClient(
        key=os.environ["TRELLO_KEY"],
        token=os.environ["TRELLO_TOKEN"],
        board_id=os.environ["TRELLO_BOARD_ID"],
    )
    discord = DiscordClient(
        webhook_url=os.environ["DISCORD_WEBHOOK_URL"],
    )
    state = load_state()

    sent = run(trello, discord, state)

    save_state(state)
    print(f"Sent {sent} notification(s).")


if __name__ == "__main__":
    main()
