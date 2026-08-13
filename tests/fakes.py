class FakeTrelloClient:
    def __init__(self, cards=None, actions=None, self_member_id="self-member"):
        self._cards = cards or []
        self._actions = actions or []
        self._self_member_id = self_member_id

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


class FakeTelegramClient:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)
