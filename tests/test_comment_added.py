from datetime import datetime
from zoneinfo import ZoneInfo

from trello_telegram_notifier import run
from tests.fakes import FakeTrelloClient, FakeTelegramClient

TZ = ZoneInfo("Asia/Manila")
NOW = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)


def comment_card_action(action_id, member_id, card_name="Ship report",
                         comment_text="Looks good to me", short_link="abc123"):
    return {
        "id": action_id,
        "type": "commentCard",
        "memberCreator": {"id": member_id, "fullName": "Jamie"},
        "data": {
            "card": {"name": card_name, "shortLink": short_link},
            "text": comment_text,
        },
    }


def test_comment_by_another_member_notifies():
    trello = FakeTrelloClient(
        cards=[],
        actions=[comment_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action0"}  # simulate a prior run already seeded the cursor

    run(trello, telegram, state, now=NOW)

    assert len(telegram.sent) == 1
    assert "Ship report" in telegram.sent[0]
    assert "Looks good to me" in telegram.sent[0]
    assert "Jamie" in telegram.sent[0]


def test_comment_by_self_is_suppressed():
    trello = FakeTrelloClient(
        cards=[],
        actions=[comment_card_action("action1", member_id="self-member")],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action0"}

    run(trello, telegram, state, now=NOW)

    assert telegram.sent == []


def test_action_cursor_is_shared_across_logged_event_types():
    from tests.test_card_created import create_card_action
    from tests.test_card_moved import move_card_action

    trello = FakeTrelloClient(
        cards=[],
        actions=[
            create_card_action("action1", member_id="other-member"),
            move_card_action("action2", member_id="other-member"),
            comment_card_action("action3", member_id="other-member"),
        ],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action0"}

    run(trello, telegram, state, now=NOW)

    assert len(telegram.sent) == 3
    assert state["action_cursor"] == "action3"


def test_already_processed_comment_action_is_not_renotified():
    trello = FakeTrelloClient(
        cards=[],
        actions=[comment_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action1"}

    run(trello, telegram, state, now=NOW)

    assert telegram.sent == []
