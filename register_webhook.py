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

import requests

TRELLO_KEY = os.environ["TRELLO_KEY"]
TRELLO_TOKEN = os.environ["TRELLO_TOKEN"]
TRELLO_BOARD_ID = os.environ["TRELLO_BOARD_ID"]


def list_webhooks():
    url = f"https://api.trello.com/1/tokens/{TRELLO_TOKEN}/webhooks"
    resp = requests.get(url, params={"key": TRELLO_KEY}, timeout=15)
    resp.raise_for_status()
    for hook in resp.json():
        print(hook["id"], hook["callbackURL"], "active" if hook["active"] else "inactive")


def delete_webhook(webhook_id):
    url = f"https://api.trello.com/1/webhooks/{webhook_id}"
    resp = requests.delete(url, params={"key": TRELLO_KEY, "token": TRELLO_TOKEN}, timeout=15)
    resp.raise_for_status()
    print(f"Deleted webhook {webhook_id}.")


def register_webhook(callback_url):
    url = "https://api.trello.com/1/webhooks"
    resp = requests.post(
        url,
        data={
            "key": TRELLO_KEY,
            "token": TRELLO_TOKEN,
            "idModel": TRELLO_BOARD_ID,
            "callbackURL": callback_url,
            "description": "Discord notifier",
        },
        timeout=15,
    )
    resp.raise_for_status()
    hook = resp.json()
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
