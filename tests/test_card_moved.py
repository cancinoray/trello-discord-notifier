from datetime import datetime
from zoneinfo import ZoneInfo

from trello_discord_notifier import run
from tests.fakes import FakeTrelloClient, FakeDiscordClient

TZ = ZoneInfo("Asia/Manila")
NOW = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)


def move_card_action(action_id, member_id, card_name="Ship report",
                      list_before="Doing", list_after="Done", short_link="abc123",
                      list_before_id="list-doing", list_after_id="list-done", card_id="card1"):
    return {
        "id": action_id,
        "type": "updateCard",
        "memberCreator": {"id": member_id},
        "data": {
            "card": {"id": card_id, "name": card_name, "shortLink": short_link},
            "listBefore": {"id": list_before_id, "name": list_before},
            "listAfter": {"id": list_after_id, "name": list_after},
        },
    }


def rename_card_action(action_id, member_id, card_name="Ship report", short_link="abc123", card_id="card1"):
    """An updateCard action that is NOT a list move (e.g. a rename)."""
    return {
        "id": action_id,
        "type": "updateCard",
        "memberCreator": {"id": member_id},
        "data": {
            "card": {"id": card_id, "name": card_name, "shortLink": short_link},
            "old": {"name": "Ship draft"},
        },
    }


def test_card_moved_by_another_member_notifies():
    trello = FakeTrelloClient(
        cards=[],
        actions=[move_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}  # simulate a prior run already seeded the cursor

    run(trello, discord, state, now=NOW)

    assert len(discord.sent) == 1
    assert "Ship report" in discord.sent[0]
    assert "Doing" in discord.sent[0]
    assert "Done" in discord.sent[0]


def test_card_moved_by_self_also_notifies():
    trello = FakeTrelloClient(
        cards=[],
        actions=[move_card_action("action1", member_id="self-member")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}

    run(trello, discord, state, now=NOW)

    assert len(discord.sent) == 1


def test_non_move_update_card_action_does_not_notify():
    trello = FakeTrelloClient(
        cards=[],
        actions=[rename_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}

    run(trello, discord, state, now=NOW)

    assert discord.sent == []


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
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}

    run(trello, discord, state, now=NOW)

    assert discord.sent == []


def test_already_processed_move_action_is_not_renotified():
    trello = FakeTrelloClient(
        cards=[],
        actions=[move_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action1"}

    run(trello, discord, state, now=NOW)

    assert discord.sent == []
