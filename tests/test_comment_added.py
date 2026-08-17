from datetime import datetime
from zoneinfo import ZoneInfo

from trello_discord_notifier import run
from tests.fakes import FakeTrelloClient, FakeDiscordClient, make_action

TZ = ZoneInfo("Asia/Manila")
NOW = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)


def comment_card_action(action_id, member_id, card_name="Ship report",
                         comment_text="Looks good to me", short_link="abc123", card_id="card1"):
    return make_action(
        "commentCard", action_id=action_id, member_creator={"id": member_id, "fullName": "Jamie"},
        card_id=card_id, card_name=card_name, short_link=short_link,
        text=comment_text,
    )


def test_comment_by_another_member_notifies():
    trello = FakeTrelloClient(
        cards=[],
        actions=[comment_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}  # simulate a prior run already seeded the cursor

    run(trello, discord, state, now=NOW)

    assert len(discord.sent) == 1
    assert "Ship report" in discord.sent[0]
    assert "Looks good to me" in discord.sent[0]
    assert "Jamie" in discord.sent[0]


def test_comment_by_self_also_notifies():
    trello = FakeTrelloClient(
        cards=[],
        actions=[comment_card_action("action1", member_id="self-member")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}

    run(trello, discord, state, now=NOW)

    assert len(discord.sent) == 1


def test_action_cursor_is_shared_across_logged_event_types():
    trello = FakeTrelloClient(
        cards=[],
        actions=[
            make_action("createCard", action_id="action1", member_id="other-member"),
            make_action(
                "updateCard", action_id="action2", member_id="other-member",
                listBefore={"id": "list-doing", "name": "Doing"},
                listAfter={"id": "list-done", "name": "Done"},
            ),
            comment_card_action("action3", member_id="other-member"),
        ],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}

    run(trello, discord, state, now=NOW)

    assert len(discord.sent) == 3
    assert state["action_cursor"] == "action3"


def test_already_processed_comment_action_is_not_renotified():
    trello = FakeTrelloClient(
        cards=[],
        actions=[comment_card_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action1"}

    run(trello, discord, state, now=NOW)

    assert discord.sent == []
