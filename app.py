#!/usr/bin/env python3
"""
Trello -> Discord notifier, webhook server.

Receives Trello board actions in real time via a registered webhook
(see register_webhook.py) and notifies Discord immediately, instead of
polling on a schedule. Due-date reminders still can't be pushed by
Trello (nothing "happens" when a deadline approaches), so they're
checked on an in-process interval instead.
"""

import asyncio
import contextlib
import logging
import os
from datetime import datetime

from fastapi import FastAPI, Request, Response

from trello_discord_notifier import (
    DiscordClient,
    HANDLED_ACTION_TYPES,
    TrelloClient,
    TZ,
    handle_logged_action,
    load_member_map,
    load_state,
    save_state,
)
from trello_discord_notifier import _process_due_soon  # noqa: F401 (internal, reused intentionally)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trello_discord_notifier")

DUE_SOON_INTERVAL_SECONDS = int(os.environ.get("DUE_SOON_INTERVAL_SECONDS", "60"))


async def due_soon_loop(app: FastAPI):
    while True:
        try:
            sent = _process_due_soon(
                app.state.trello, app.state.discord, app.state.notifier_state, datetime.now(TZ),
                app.state.member_map,
            )
            save_state(app.state.notifier_state)
            if sent:
                logger.info("Sent %d due-soon notification(s).", sent)
        except Exception:
            logger.exception("due-soon check failed")
        await asyncio.sleep(DUE_SOON_INTERVAL_SECONDS)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Tests pre-populate app.state with fakes before startup (see tests/test_app.py);
    # only fall back to real construction for whatever isn't already set.
    if not hasattr(app.state, "trello"):
        app.state.trello = TrelloClient(
            key=os.environ["TRELLO_KEY"],
            token=os.environ["TRELLO_TOKEN"],
            board_id=os.environ["TRELLO_BOARD_ID"],
        )
    if not hasattr(app.state, "discord"):
        app.state.discord = DiscordClient(webhook_url=os.environ["DISCORD_WEBHOOK_URL"])
    if not hasattr(app.state, "member_map"):
        app.state.member_map = load_member_map()
    if not hasattr(app.state, "notifier_state"):
        app.state.notifier_state = load_state()

    task = asyncio.create_task(due_soon_loop(app))
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(lifespan=lifespan)


@app.head("/trello-webhook")
async def verify_webhook():
    """Trello requires a HEAD 200 on this URL before it will register the webhook."""
    return Response(status_code=200)


@app.post("/trello-webhook")
async def receive_webhook(request: Request):
    body = await request.json()
    action = body.get("action")
    if action is None:
        # Trello also POSTs here for webhook lifecycle pings with no action payload.
        return Response(status_code=200)

    if action["type"] not in HANDLED_ACTION_TYPES:
        return Response(status_code=200)

    try:
        sent = handle_logged_action(
            request.app.state.trello, request.app.state.discord, action, request.app.state.member_map
        )
        if sent:
            logger.info("Notified Discord for action %s (%s).", action["id"], action["type"])
    except Exception:
        logger.exception("Failed to handle Trello action %s", action.get("id"))

    return Response(status_code=200)


@app.get("/health")
async def health():
    return {"status": "ok"}
