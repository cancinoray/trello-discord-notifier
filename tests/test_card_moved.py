from datetime import datetime
from zoneinfo import ZoneInfo

from trello_telegram_notifier import run
from tests.fakes import FakeTrelloClient, FakeTelegramClient

TZ = ZoneInfo("Asia/Manila")
NOW = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)


def move_card_action(action_id, member_id, card_name="Ship report",
                      list_before="Doing", list_after="Done", short_link="abc123",
                      list_before_id="list-doing", list_after_id="list-done"):
    return {
        "id": action_id,
        "type": "updateCard",
        "memberCreator": {"id": member_id},
        "data": {
            "card": {"name": card_name, "shortLink": short_link},
            "listBefore": {"id": list_before_id, "name": list_before},
            "listAfter": {"id": list_after_id, "name": list_after},
        },
    }


def rename_card_action(action_id, member_id, card_name="Ship report", short_link="abc123"):
    """An updateCard action that is NOT a list move (e.g. a rename)."""
    return {
        "id": action_id,
        "type": "updateCard",
        "memberCreator": {"id": member_id},
        "data": {
            "card": {"name": card_name, "shortLink": short_link},
            "old": {"name": "Ship draft"},
        },
    }


def test_card_moved_by_another_member_notifies():
    trello = FakeTrelloClient(
        cards=[],
        actions=[move_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action0"}  # simulate a prior run already seeded the cursor

    run(trello, telegram, state, now=NOW)

    assert len(telegram.sent) == 1
    assert "Ship report" in telegram.sent[0]
    assert "Doing" in telegram.sent[0]
    assert "Done" in telegram.sent[0]


def test_card_moved_by_self_is_suppressed():
    trello = FakeTrelloClient(
        cards=[],
        actions=[move_card_action("action1", member_id="self-member")],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action0"}

    run(trello, telegram, state, now=NOW)

    assert telegram.sent == []


def test_non_move_update_card_action_does_not_notify():
    trello = FakeTrelloClient(
        cards=[],
        actions=[rename_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action0"}

    run(trello, telegram, state, now=NOW)

    assert telegram.sent == []


def test_update_card_with_same_list_before_and_after_does_not_notify():
    """listBefore/listAfter present but identical (e.g. a card copy within the same list) is not a move."""
    trello = FakeTrelloClient(
        cards=[],
        actions=[move_card_action(
            "action1", member_id="other-member",
            list_before="Doing", list_after="Doing",
            list_before_id="list-doing", list_after_id="list-doing",
        )],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action0"}

    run(trello, telegram, state, now=NOW)

    assert telegram.sent == []


def test_already_processed_move_action_is_not_renotified():
    trello = FakeTrelloClient(
        cards=[],
        actions=[move_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    telegram = FakeTelegramClient()
    state = {"action_cursor": "action1"}

    run(trello, telegram, state, now=NOW)

    assert telegram.sent == []
