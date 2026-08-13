from datetime import datetime
from zoneinfo import ZoneInfo

from trello_telegram_notifier import run
from tests.fakes import FakeTrelloClient, FakeTelegramClient

TZ = ZoneInfo("Asia/Manila")
NOW = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)


def create_card_action(action_id, member_id, card_name="New card", short_link="abc123"):
    return {
        "id": action_id,
        "type": "createCard",
        "memberCreator": {"id": member_id},
        "data": {
            "card": {"name": card_name, "shortLink": short_link},
        },
    }


def test_card_created_by_another_member_notifies():
    trello = FakeTrelloClient(
        cards=[],
        actions=[create_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action0"}  # simulate a prior run already seeded the cursor

    run(trello, telegram, state, now=NOW)

    assert len(telegram.sent) == 1
    assert "New card" in telegram.sent[0]


def test_card_created_by_self_is_suppressed():
    trello = FakeTrelloClient(
        cards=[],
        actions=[create_card_action("action1", member_id="self-member")],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action0"}

    run(trello, telegram, state, now=NOW)

    assert telegram.sent == []


def test_first_run_seeds_cursor_without_notifying_on_backlog():
    trello = FakeTrelloClient(
        cards=[],
        actions=[
            create_card_action("action1", member_id="other-member"),
            create_card_action("action2", member_id="other-member"),
        ],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {}  # no action_cursor yet: first run ever

    run(trello, telegram, state, now=NOW)

    assert telegram.sent == []
    assert state["action_cursor"] == "action2"


def test_already_processed_action_is_not_renotified():
    trello = FakeTrelloClient(
        cards=[],
        actions=[create_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action1"}

    run(trello, telegram, state, now=NOW)

    assert telegram.sent == []
