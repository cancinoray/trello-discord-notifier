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


def test_rename_action_notifies_as_card_renamed():
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

    assert result is True
    assert "Old name" in discord.sent[0]
    assert "Renamed card" in discord.sent[0]


def test_description_edit_notifies_as_card_updated():
    trello = FakeTrelloClient()
    discord = FakeDiscordClient()
    action = {
        "id": "action1",
        "type": "updateCard",
        "memberCreator": {"id": "member1"},
        "data": {
            "card": {"id": "card1", "name": "Some card", "shortLink": "abc123"},
            "old": {"desc": ""},
        },
    }

    result = handle_logged_action(trello, discord, action, member_map={})

    assert result is True
    assert "Some card" in discord.sent[0]


def test_update_card_action_unrelated_to_tracked_fields_is_skipped():
    """An updateCard whose `old` payload has neither name/desc/list keys
    (e.g. due date change, label change) isn't a tracked Event Type."""
    trello = FakeTrelloClient()
    discord = FakeDiscordClient()
    action = {
        "id": "action1",
        "type": "updateCard",
        "memberCreator": {"id": "member1"},
        "data": {
            "card": {"id": "card1", "name": "Some card", "shortLink": "abc123"},
            "old": {"due": None},
        },
    }

    result = handle_logged_action(trello, discord, action, member_map={})

    assert result is False
    assert discord.sent == []


def test_create_list_action_notifies():
    trello = FakeTrelloClient()
    discord = FakeDiscordClient()
    action = {
        "id": "action1",
        "type": "createList",
        "memberCreator": {"id": "member1"},
        "data": {"list": {"id": "list1", "name": "New list"}},
    }

    result = handle_logged_action(trello, discord, action, member_map={})

    assert result is True
    assert "New list" in discord.sent[0]
