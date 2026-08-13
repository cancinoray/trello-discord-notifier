from datetime import datetime
from zoneinfo import ZoneInfo

from trello_telegram_notifier import run
from tests.fakes import FakeTrelloClient, FakeTelegramClient

TZ = ZoneInfo("Asia/Manila")


def test_checkpoint_fires_when_in_window_and_not_already_sent():
    now = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)
    due = datetime(2026, 8, 14, 8, 5, tzinfo=TZ)  # 1 day before checkpoint window
    trello = FakeTrelloClient(cards=[
        {"id": "card1", "name": "Ship report", "due": due.isoformat(), "dueComplete": False, "shortUrl": "https://trello.com/c/card1"},
    ])
    telegram = FakeTelegramClient()
    state = {}

    run(trello, telegram, state, now=now)

    assert len(telegram.sent) == 1
    assert "Ship report" in telegram.sent[0]
    assert "Due tomorrow" in telegram.sent[0]


def test_checkpoint_does_not_refire_if_already_sent():
    now = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)
    due = datetime(2026, 8, 14, 8, 5, tzinfo=TZ)
    trello = FakeTrelloClient(cards=[
        {"id": "card1", "name": "Ship report", "due": due.isoformat(), "dueComplete": False, "shortUrl": "https://trello.com/c/card1"},
    ])
    telegram = FakeTelegramClient()
    state = {"cards": {"card1": {"day_before_8am": True}}}

    run(trello, telegram, state, now=now)

    assert telegram.sent == []


def test_checkpoint_does_not_fire_outside_firing_window():
    now = datetime(2026, 8, 13, 9, 0, tzinfo=TZ)  # 55 min after the 8am checkpoint, window is 20 min
    due = datetime(2026, 8, 14, 8, 5, tzinfo=TZ)
    trello = FakeTrelloClient(cards=[
        {"id": "card1", "name": "Ship report", "due": due.isoformat(), "dueComplete": False, "shortUrl": "https://trello.com/c/card1"},
    ])
    telegram = FakeTelegramClient()
    state = {}

    run(trello, telegram, state, now=now)

    assert telegram.sent == []


def test_state_pruned_for_cards_no_longer_open_or_due():
    now = datetime(2026, 8, 13, 8, 5, tzinfo=TZ)
    trello = FakeTrelloClient(cards=[])  # card1 completed/archived/removed
    telegram = FakeTelegramClient()
    state = {"cards": {"card1": {"day_before_8am": True}}}

    run(trello, telegram, state, now=now)

    assert "card1" not in state["cards"]
