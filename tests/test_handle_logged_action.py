from trello_discord_notifier import handle_logged_action
from tests.fakes import FakeTrelloClient, FakeDiscordClient


def test_create_card_action_notifies_and_returns_true():
    trello = FakeTrelloClient(card_members={"card1": []})
    discord = FakeDiscordClient()
    action = {
        "id": "action1",
        "type": "createCard",
        "memberCreator": {"id": "member1"},
        "data": {"card": {"id": "card1", "name": "New card", "shortLink": "abc123"}},
    }

    result = handle_logged_action(trello, discord, action, member_map={})

    assert result is True
    assert len(discord.sent) == 1
    assert "New card" in discord.sent[0]


def test_rename_action_is_skipped_and_returns_false():
    """An updateCard that isn't a list move (e.g. a rename) shouldn't notify."""
    trello = FakeTrelloClient()
    discord = FakeDiscordClient()
    action = {
        "id": "action1",
        "type": "updateCard",
        "memberCreator": {"id": "member1"},
        "data": {
            "card": {"id": "card1", "name": "Renamed card", "shortLink": "abc123"},
            "old": {"name": "Old name"},
        },
    }

    result = handle_logged_action(trello, discord, action, member_map={})

    assert result is False
    assert discord.sent == []
