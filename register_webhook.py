#!/usr/bin/env python3
"""
One-off script to register (or list/delete) the Trello webhook that
points at the deployed app.py server's /trello-webhook endpoint.

Usage:
    uv run register_webhook.py <callback-url>
    uv run register_webhook.py --list
    uv run register_webhook.py --delete <webhook-id>
"""

import os
import sys

from trello_discord_notifier import TrelloClient

trello = TrelloClient(
    key=os.environ["TRELLO_KEY"],
    token=os.environ["TRELLO_TOKEN"],
    board_id=os.environ["TRELLO_BOARD_ID"],
)


def list_webhooks():
    for hook in trello.list_webhooks():
        print(hook["id"], hook["callbackURL"], "active" if hook["active"] else "inactive")


def delete_webhook(webhook_id):
    trello.delete_webhook(webhook_id)
    print(f"Deleted webhook {webhook_id}.")


def register_webhook(callback_url):
    hook = trello.register_webhook(callback_url)
    print(f"Registered webhook {hook['id']} -> {hook['callbackURL']}")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--list":
        list_webhooks()
    elif len(sys.argv) == 3 and sys.argv[1] == "--delete":
        delete_webhook(sys.argv[2])
    elif len(sys.argv) == 2:
        register_webhook(sys.argv[1])
    else:
        print(__doc__)
        sys.exit(1)
