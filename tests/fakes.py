class FakeTrelloClient:
    def __init__(self, cards=None, actions=None, self_member_id="self-member", card_members=None):
        self._cards = cards or []
        self._actions = actions or []
        self._self_member_id = self_member_id
        self._card_members = card_members or {}

    def fetch_due_cards(self):
        return [c for c in self._cards if c.get("due") and not c.get("dueComplete")]

    def fetch_actions_since(self, cursor):
        """Actions are stored oldest-first; return everything after `cursor` (exclusive)."""
        if cursor is None:
            return list(self._actions)
        idx = next((i for i, a in enumerate(self._actions) if a["id"] == cursor), -1)
        return self._actions[idx + 1:]

    def fetch_self_member_id(self):
        return self._self_member_id

    def fetch_card_members(self, card_id):
        return self._card_members.get(card_id, [])


def make_action(action_type, action_id="action1", member_id="other-member",
                 member_creator=None, card_id="card1", card_name="Ship report",
                 short_link="abc123", card=None, **extra_data):
    """Build a Trello Action payload shaped like the Actions API / webhook body.

    `card` overrides the default {id, name, shortLink} card dict entirely, for
    action types with no card (e.g. createList) — pass card=None explicitly via
    an action type that doesn't need one, or pass a full replacement dict.
    Any extra keyword becomes an additional `data` key (e.g. text=..., old=...,
    member=..., listBefore=..., list=...).
    """
    data = dict(extra_data)
    if card is not False:
        data["card"] = card or {"id": card_id, "name": card_name, "shortLink": short_link}
    return {
        "id": action_id,
        "type": action_type,
        "memberCreator": member_creator or {"id": member_id},
        "data": data,
    }


class FakeDiscordClient:
    """Records embeds sent via send_embed(). `sent` holds a searchable text
    representation of each embed (title + description) so existing tests can
    keep asserting on message content with `in`, without inspecting embed
    structure directly; `embeds` holds the raw dicts for structural assertions."""

    def __init__(self):
        self.sent = []
        self.embeds = []

    def send_embed(self, title, description, color, url=None):
        embed = {"title": title, "description": description, "color": color, "url": url}
        self.embeds.append(embed)
        self.sent.append(f"{title}\n{description}\n{url or ''}")
