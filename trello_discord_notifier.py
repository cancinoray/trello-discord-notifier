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
STATE_FILE = os.environ.get(
    "STATE_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json"),
)

TZ = ZoneInfo(TIMEZONE)

LABELS = {
    "day_before_8am": "Due tomorrow",
    "same_day_8am": "Due today",
    "30min_before": "Due in 30 minutes",
}

# Discord embed side-bar colors, one per Event Type.
COLOR_DUE_SOON = 0xE74C3C     # red
COLOR_CARD_CREATED = 0x2ECC71  # green
COLOR_CARD_MOVED = 0x3498DB    # blue
COLOR_COMMENT_ADDED = 0xF1C40F  # gold


def load_member_map():
    """Parse DISCORD_MEMBER_MAP ("trelloId1:discordId1,trelloId2:discordId2")
    into a dict of Trello member id -> Discord user id, used to @mention assignees."""
    raw = os.environ.get("DISCORD_MEMBER_MAP", "")
    pairs = (pair.split(":", 1) for pair in raw.split(",") if ":" in pair)
    return {trello_id.strip(): discord_id.strip() for trello_id, discord_id in pairs}


def mentions_line(members, member_map):
    """Build a 'Assigned: @user1 @user2' line for a card's assigned members.
    Members without a Discord mapping fall back to their Trello name."""
    if not members:
        return None
    mentions = [
        f"<@{member_map[m['id']]}>" if m["id"] in member_map else m["fullName"]
        for m in members
    ]
    return f"Assigned: {', '.join(mentions)}"


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

    def fetch_card_members(self, card_id):
        """Return the Trello members currently assigned to a card."""
        url = f"https://api.trello.com/1/cards/{card_id}/members"
        params = {"key": self._key, "token": self._token, "fields": "id,fullName"}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def list_webhooks(self):
        """Return all webhooks registered against this client's token."""
        url = f"https://api.trello.com/1/tokens/{self._token}/webhooks"
        resp = requests.get(url, params={"key": self._key}, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def register_webhook(self, callback_url, description="Discord notifier"):
        """Register a webhook against this client's board, calling back to `callback_url`."""
        url = "https://api.trello.com/1/webhooks"
        resp = requests.post(
            url,
            data={
                "key": self._key,
                "token": self._token,
                "idModel": self._board_id,
                "callbackURL": callback_url,
                "description": description,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def delete_webhook(self, webhook_id):
        """Delete a previously registered webhook by id."""
        url = f"https://api.trello.com/1/webhooks/{webhook_id}"
        resp = requests.delete(url, params={"key": self._key, "token": self._token}, timeout=15)
        resp.raise_for_status()


class DiscordClient:
    def __init__(self, webhook_url):
        self._webhook_url = webhook_url

    def send_embed(self, title, description, color, url=None):
        embed = {"title": title, "description": description, "color": color}
        if url:
            embed["url"] = url
        resp = requests.post(
            self._webhook_url,
            json={"embeds": [embed]},
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


def _process_due_soon(trello, discord, state, now, member_map=None):
    if member_map is None:
        member_map = {}
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
                mentions = mentions_line(trello.fetch_card_members(card_id), member_map)
                description = f"**{card['name']}**\nDue: {due_local.strftime('%b %d, %I:%M %p')}"
                if mentions:
                    description += f"\n{mentions}"
                discord.send_embed(
                    title=f"⏰ {LABELS[key]}",
                    description=description,
                    color=COLOR_DUE_SOON,
                    url=card["shortUrl"],
                )
                card_state[key] = True
                sent += 1

    # Drop state for cards that are no longer open/due (completed, deleted, etc.)
    for cid in list(checkpoints.keys()):
        if cid not in current_ids:
            del checkpoints[cid]

    return sent


def handle_logged_action(trello, discord, action, member_map):
    """Notify Discord for a single Logged Event (createCard/updateCard/commentCard).
    Returns True if a notification was sent, False if the action was skipped
    (e.g. an updateCard that wasn't a list move)."""
    card = action["data"]["card"]
    card_url = f"https://trello.com/c/{card['shortLink']}"
    if action["type"] == "createCard":
        mentions = mentions_line(trello.fetch_card_members(card["id"]), member_map)
        description = f"**{card['name']}**"
        if mentions:
            description += f"\n{mentions}"
        discord.send_embed(
            title="🆕 Card created", description=description, color=COLOR_CARD_CREATED, url=card_url
        )
        return True
    elif (
        action["type"] == "updateCard"
        and "listBefore" in action["data"]
        and action["data"]["listBefore"]["id"] != action["data"]["listAfter"]["id"]
    ):
        list_before = action["data"]["listBefore"]["name"]
        list_after = action["data"]["listAfter"]["name"]
        mentions = mentions_line(trello.fetch_card_members(card["id"]), member_map)
        description = f"**{card['name']}**\n{list_before} → {list_after}"
        if mentions:
            description += f"\n{mentions}"
        discord.send_embed(
            title="➡️ Card moved", description=description, color=COLOR_CARD_MOVED, url=card_url
        )
        return True
    elif action["type"] == "commentCard":
        commenter = action["memberCreator"]["fullName"]
        mentions = mentions_line(trello.fetch_card_members(card["id"]), member_map)
        description = f"**{card['name']}**\n{commenter}: {action['data']['text']}"
        if mentions:
            description += f"\n{mentions}"
        discord.send_embed(
            title="💬 New comment", description=description, color=COLOR_COMMENT_ADDED, url=card_url
        )
        return True
    return False


def _process_logged_events(trello, discord, state, self_member_id, member_map, now):
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
        if handle_logged_action(trello, discord, action, member_map):
            sent += 1

    if actions:
        state["action_cursor"] = actions[-1]["id"]

    return sent


def run(trello, discord, state, member_map=None, now=None):
    """Orchestrate a single check: due-soon reminders plus board-activity notifications.
    Used by the polling entrypoint (main); the webhook server calls
    handle_logged_action directly per-action instead."""
    if now is None:
        now = datetime.now(TZ)
    if member_map is None:
        member_map = {}

    # Polling-only: the webhook adapter never calls run(), so self_member_id
    # is never populated in state.json under a webhook-only deployment.
    self_member_id = trello.fetch_self_member_id()
    state["self_member_id"] = self_member_id

    sent = _process_due_soon(trello, discord, state, now, member_map)
    sent += _process_logged_events(trello, discord, state, self_member_id, member_map, now)

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
    member_map = load_member_map()

    sent = run(trello, discord, state, member_map=member_map)

    save_state(state)
    print(f"Sent {sent} notification(s).")


if __name__ == "__main__":
    main()
