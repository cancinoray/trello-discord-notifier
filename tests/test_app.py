import atexit
import os
import shutil
import tempfile

# Must be set before trello_discord_notifier (and therefore app) is imported,
# since STATE_FILE is resolved once at module import time — otherwise tests
# would read/write the real repo's state.json.
_state_dir = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _state_dir, ignore_errors=True)
os.environ.setdefault("STATE_FILE", os.path.join(_state_dir, "state.json"))
os.environ.setdefault("DUE_SOON_INTERVAL_SECONDS", "3600")

from fastapi.testclient import TestClient  # noqa: E402 (must follow STATE_FILE setup above)

import app as app_module  # noqa: E402
from trello_discord_notifier import HANDLED_ACTION_TYPES, TrelloClient  # noqa: E402
from tests.fakes import FakeDiscordClient, FakeTrelloClient, make_action  # noqa: E402


class RaisingTrelloClient(FakeTrelloClient):
    """A FakeTrelloClient whose fetch_due_cards always raises, to exercise
    due_soon_loop's exception-swallowing without a real failure scenario."""

    def fetch_due_cards(self):
        raise RuntimeError("boom")


def make_client(trello=None, discord=None, member_map=None, notifier_state=None):
    """Build a TestClient with fakes pre-populated on app.state before startup,
    so app.py's lifespan (which only fills in what's missing) never touches
    real credentials or the real state.json."""
    app_module.app.state.trello = trello or FakeTrelloClient()
    app_module.app.state.discord = discord or FakeDiscordClient()
    app_module.app.state.member_map = member_map if member_map is not None else {}
    app_module.app.state.notifier_state = notifier_state if notifier_state is not None else {}
    return TestClient(app_module.app)


def test_create_card_webhook_notifies_discord():
    discord = FakeDiscordClient()
    trello = FakeTrelloClient(card_members={"card1": []})
    client = make_client(trello=trello, discord=discord)

    with client:
        resp = client.post("/trello-webhook", json={"action": make_action("createCard", member_id="member1", card_name="New card")})

    assert resp.status_code == 200
    assert len(discord.sent) == 1
    assert "New card" in discord.sent[0]


def test_lifecycle_ping_with_no_action_does_not_notify():
    discord = FakeDiscordClient()
    client = make_client(discord=discord)

    with client:
        resp = client.post("/trello-webhook", json={})

    assert resp.status_code == 200
    assert discord.sent == []


def test_action_type_outside_allowlist_does_not_notify():
    discord = FakeDiscordClient()
    client = make_client(discord=discord)
    action = {"id": "action1", "type": "updateBoard", "data": {}}

    with client:
        resp = client.post("/trello-webhook", json={"action": action})

    assert resp.status_code == 200
    assert discord.sent == []


def test_exception_in_handle_logged_action_is_swallowed_and_returns_200(caplog):
    discord = FakeDiscordClient()

    class RaisingTrelloForAction(FakeTrelloClient):
        def fetch_card_members(self, card_id):
            raise RuntimeError("boom")

    client = make_client(trello=RaisingTrelloForAction(), discord=discord)

    with client, caplog.at_level("ERROR", logger="trello_discord_notifier"):
        resp = client.post("/trello-webhook", json={"action": make_action("createCard", member_id="member1", card_name="New card")})

    assert resp.status_code == 200
    assert discord.sent == []
    assert "Failed to handle Trello action" in caplog.text


def test_head_webhook_returns_200_with_empty_body():
    client = make_client()

    with client:
        resp = client.head("/trello-webhook")

    assert resp.status_code == 200
    assert resp.content == b""


def test_due_soon_loop_exception_does_not_propagate():
    """due_soon_loop runs its body once immediately on startup (before its first
    sleep) — if fetch_due_cards raises, the loop must catch it, not crash the
    background task or the app startup."""
    client = make_client(trello=RaisingTrelloClient())

    with client:
        resp = client.get("/health")

    assert resp.status_code == 200


def test_polling_filter_is_built_from_handled_action_types(monkeypatch):
    """TrelloClient.fetch_actions_since's polling filter string must be built
    from HANDLED_ACTION_TYPES, not a separately hand-typed list, so it can't
    silently diverge from app.py's webhook allowlist (which reads the same
    constant — see test_webhook_allowlist_matches_handled_action_types)."""
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return []

    def fake_get(url, params, timeout):
        captured.update(params)
        return FakeResponse()

    monkeypatch.setattr("trello_discord_notifier.requests.get", fake_get)

    trello = TrelloClient(key="k", token="t", board_id="b")
    trello.fetch_actions_since(cursor=None)

    assert set(captured["filter"].split(",")) == set(HANDLED_ACTION_TYPES)


def test_webhook_allowlist_matches_handled_action_types(monkeypatch):
    """Every type in HANDLED_ACTION_TYPES reaches handle_logged_action; nothing
    outside it does. Confirms the allowlist check in receive_webhook reads the
    shared constant rather than its own hand-typed tuple, so it can't silently
    diverge from the polling filter. Spies on handle_logged_action directly,
    decoupled from any Event Type's own notify conditions (already covered by
    the per-Event-Type test files)."""
    calls = []
    monkeypatch.setattr(
        app_module, "handle_logged_action",
        lambda trello, discord, action, member_map: calls.append(action["type"]) or True,
    )

    client = make_client()
    with client:
        for action_type in HANDLED_ACTION_TYPES:
            resp = client.post("/trello-webhook", json={"action": {"id": "a1", "type": action_type, "data": {}}})
            assert resp.status_code == 200

        resp = client.post("/trello-webhook", json={"action": {"id": "a2", "type": "updateBoard", "data": {}}})
        assert resp.status_code == 200

    assert calls == list(HANDLED_ACTION_TYPES)
