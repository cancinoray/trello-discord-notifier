from datetime import datetime
from zoneinfo import ZoneInfo

from trello_discord_notifier import run
from tests.fakes import FakeTrelloClient, FakeDiscordClient

TZ = ZoneInfo("Asia/Manila")


def test_self_member_id_is_resolved_and_cached_in_state():
    now = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)
    trello = FakeTrelloClient(cards=[], self_member_id="member-42")
    discord = FakeDiscordClient()
    state = {}

    run(trello, discord, state, now=now)

    assert state["self_member_id"] == "member-42"
