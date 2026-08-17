from datetime import datetime
from zoneinfo import ZoneInfo

from trello_discord_notifier import run
from tests.fakes import FakeTrelloClient, FakeDiscordClient

TZ = ZoneInfo("Asia/Manila")


def test_checkpoint_fires_when_in_window_and_not_already_sent():
    now = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)
    due = datetime(2026, 8, 14, 8, 5, tzinfo=TZ)  # 1 day before checkpoint window
    trello = FakeTrelloClient(cards=[
        {"id": "card1", "name": "Ship report", "due": due.isoformat(), "dueComplete": False, "shortUrl": "https://trello.com/c/card1"},
    ])
    discord = FakeDiscordClient()
    state = {}

    run(trello, discord, state, now=now)

    assert len(discord.sent) == 1
    assert "Ship report" in discord.sent[0]
    assert "Due tomorrow" in discord.sent[0]


def test_checkpoint_does_not_refire_if_already_sent():
    now = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)
    due = datetime(2026, 8, 14, 8, 5, tzinfo=TZ)
    trello = FakeTrelloClient(cards=[
        {"id": "card1", "name": "Ship report", "due": due.isoformat(), "dueComplete": False, "shortUrl": "https://trello.com/c/card1"},
    ])
    discord = FakeDiscordClient()
    state = {"cards": {"card1": {"day_before_8am": True}}}

    run(trello, discord, state, now=now)

    assert discord.sent == []


def test_checkpoint_does_not_fire_outside_firing_window():
    now = datetime(2026, 8, 13, 9, 0, tzinfo=TZ)  # 55 min after the 8am checkpoint, window is 20 min
    due = datetime(2026, 8, 14, 8, 5, tzinfo=TZ)
    trello = FakeTrelloClient(cards=[
        {"id": "card1", "name": "Ship report", "due": due.isoformat(), "dueComplete": False, "shortUrl": "https://trello.com/c/card1"},
    ])
    discord = FakeDiscordClient()
    state = {}

    run(trello, discord, state, now=now)

    assert discord.sent == []


def test_state_pruned_for_cards_no_longer_open_or_due():
    now = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)
    trello = FakeTrelloClient(cards=[])  # card1 completed/archived/removed
    discord = FakeDiscordClient()
    state = {"cards": {"card1": {"day_before_8am": True}}}

    run(trello, discord, state, now=now)

    assert "card1" not in state["cards"]


def test_due_soon_reminder_includes_assignee_mention():
    now = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)
    due = datetime(2026, 8, 14, 8, 5, tzinfo=TZ)
    trello = FakeTrelloClient(
        cards=[
            {"id": "card1", "name": "Ship report", "due": due.isoformat(), "dueComplete": False, "shortUrl": "https://trello.com/c/card1"},
        ],
        card_members={"card1": [{"id": "trello-jamie", "fullName": "Jamie"}]},
    )
    discord = FakeDiscordClient()
    state = {}

    run(trello, discord, state, member_map={"trello-jamie": "111222333"}, now=now)

    assert len(discord.sent) == 1
    assert "<@111222333>" in discord.sent[0]
