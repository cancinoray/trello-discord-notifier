from datetime import datetime
from zoneinfo import ZoneInfo

from trello_discord_notifier import run
from tests.fakes import FakeTrelloClient, FakeDiscordClient

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
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}  # simulate a prior run already seeded the cursor

    run(trello, discord, state, now=NOW)

    assert len(discord.sent) == 1
    assert "New card" in discord.sent[0]


def test_card_created_by_self_is_suppressed():
    trello = FakeTrelloClient(
        cards=[],
        actions=[create_card_action("action1", member_id="self-member")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}

    run(trello, discord, state, now=NOW)

    assert discord.sent == []


def test_first_run_seeds_cursor_without_notifying_on_backlog():
    trello = FakeTrelloClient(
        cards=[],
        actions=[
            create_card_action("action1", member_id="other-member"),
            create_card_action("action2", member_id="other-member"),
        ],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {}  # no action_cursor yet: first run ever

    run(trello, discord, state, now=NOW)

    assert discord.sent == []
    assert state["action_cursor"] == "action2"


def test_first_run_with_no_actions_still_seeds_cursor():
    """A cursor must be written even on an empty first fetch, or every subsequent
    run keeps looking like 'first run' and silently swallows the next real action."""
    trello = FakeTrelloClient(cards=[], actions=[], self_member_id="self-member")
    discord = FakeDiscordClient()
    state = {}

    run(trello, discord, state, now=NOW)

    assert discord.sent == []
    assert "action_cursor" in state

    # Second run: a real action shows up and must notify, not be treated as backlog.
    trello_second_run = FakeTrelloClient(
        cards=[],
        actions=[create_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    run(trello_second_run, discord, state, now=NOW)

    assert len(discord.sent) == 1


def test_already_processed_action_is_not_renotified():
    trello = FakeTrelloClient(
        cards=[],
        actions=[create_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action1"}

    run(trello, discord, state, now=NOW)

    assert discord.sent == []
