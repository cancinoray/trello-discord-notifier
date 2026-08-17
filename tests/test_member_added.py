from datetime import datetime
from zoneinfo import ZoneInfo

from trello_discord_notifier import run
from tests.fakes import FakeTrelloClient, FakeDiscordClient

TZ = ZoneInfo("Asia/Manila")
NOW = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)


def add_member_action(action_id, member_id, added_member_id="jamie", added_member_name="Jamie",
                       card_name="Ship report", short_link="abc123", card_id="card1"):
    return {
        "id": action_id,
        "type": "addMemberToCard",
        "memberCreator": {"id": member_id},
        "data": {
            "idMember": added_member_id,
            "member": {"id": added_member_id, "name": added_member_name},
            "card": {"id": card_id, "name": card_name, "shortLink": short_link},
        },
    }


def test_member_added_notifies_with_plain_name_when_unmapped():
    trello = FakeTrelloClient(
        cards=[],
        actions=[add_member_action("action1", member_id="other-member")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}

    run(trello, discord, state, now=NOW)

    assert len(discord.sent) == 1
    assert "Ship report" in discord.sent[0]
    assert "Jamie" in discord.sent[0]


def test_member_added_mentions_discord_user_when_mapped():
    trello = FakeTrelloClient(
        cards=[],
        actions=[add_member_action("action1", member_id="other-member", added_member_id="jamie")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}

    run(trello, discord, state, member_map={"jamie": "111222333"}, now=NOW)

    assert "<@111222333>" in discord.sent[0]


def test_member_added_by_self_also_notifies():
    trello = FakeTrelloClient(
        cards=[],
        actions=[add_member_action("action1", member_id="self-member")],
        self_member_id="self-member",
    )
    discord = FakeDiscordClient()
    state = {"action_cursor": "action0"}

    run(trello, discord, state, now=NOW)

    assert len(discord.sent) == 1
