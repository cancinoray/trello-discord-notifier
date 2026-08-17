# Trello → Discord Notifier

Sends you a Discord message — as a color-coded embed, not plain text — when things worth noticing happen on your Trello board.

**Due-date reminders** (⏰ red), for cards with a due date set and not marked complete:

- 1 day before, at 8:00 AM
- Same day, at 8:00 AM (skipped if the deadline itself is before 8am)
- 30 minutes before the due time

**Board activity**, for any member's action on the board:

- 🆕 Card created (green)
- ➡️ Card moved between lists (blue)
- 💬 Comment added (gold)

Every message shows the card as a clickable link, and — if the card has assigned Trello members — an "Assigned" line naming them (see [Mention assignees](#4-optional-mention-assignees-in-discord) below).

Two ways to run it:

- **Railway** (webhooks, real-time) — an always-on server that Trello pushes to instantly. See [Real-time on Railway](#real-time-on-railway). **This is the currently deployed setup.**
- **GitHub Actions** (polling, every 5 minutes) — free, no server needed. See steps below. Kept as documented fallback; its schedule is currently disabled in favor of Railway (`workflow_dispatch` still works for manual runs/testing).

## 1. Create a Discord webhook

1. In Discord, go to the channel you want notifications in → **Edit Channel → Integrations → Webhooks → New Webhook**.
2. Give it a name/avatar if you like, then click **Copy Webhook URL**. This is `DISCORD_WEBHOOK_URL`.

## 2. Get Trello credentials

1. Go to [trello.com/power-ups/admin](https://trello.com/power-ups/admin/) (or [trello.com/app-key](https://trello.com/app-key)) while logged in, and click **New** to create an app if you don't have one yet — copy its **API Key**. This is `TRELLO_KEY`.
2. On the same page, click the link to manually generate a **Token** (grants read access) → copy it. This is `TRELLO_TOKEN`.
3. Get your board ID: open your board in the browser and add `.json` to the end of the URL, then find the `"id"` field near the top — a 24-character string like `6a7d808f927029f4cf5dab57`. This is `TRELLO_BOARD_ID`. **Use this full id, not the short one from the URL itself** (the string after `/b/`, e.g. `AbCd1234`) — the short id works for most API calls but Trello's webhook registration (`register_webhook.py`, used for the Railway setup) rejects it with `invalid value for idModel`.

## 3. Push this project to GitHub

If you haven't already:

```bash
cd trello-discord-notifier
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/trello-discord-notifier.git
git push -u origin main
```

Tip: make the repo **public** for unlimited free GitHub Actions minutes. If you'd rather keep it private, you get 2,000 free minutes/month on a personal account, which is enough for a 15-minute schedule.

## 4. (Optional) Mention assignees in Discord

If a card has assigned Trello members, every message type — due-date reminders and board activity alike — can `@mention` them in Discord instead of just printing their Trello name. This requires mapping each Trello member's id to their Discord user id, since the two platforms have no built-in link.

1. Get each teammate's Trello member id: `https://api.trello.com/1/boards/<TRELLO_BOARD_ID>/members?key=<TRELLO_KEY>&token=<TRELLO_TOKEN>` (open in a browser while logged in) lists every board member's `id`.
2. Get their Discord user id: in Discord, enable **Settings → Advanced → Developer Mode**, then right-click their name → **Copy User ID**.
3. Build a comma-separated `trelloId:discordId` list, e.g. `abc123:111222333,def456:444555666`. This is `DISCORD_MEMBER_MAP`.

Members not in the map still show up in the message, just as their plain Trello name instead of a mention.

## 5. Add your secrets

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**. Add:

- `TRELLO_KEY`
- `TRELLO_TOKEN`
- `TRELLO_BOARD_ID`
- `DISCORD_WEBHOOK_URL`
- `DISCORD_MEMBER_MAP` (optional — only if you set up assignee mentions above)

## 6. (Optional) Run it locally first

Copy the same values into `.envrc` (gitignored) to test before relying on the schedule:

```bash
export TRELLO_KEY="..."
export TRELLO_TOKEN="..."
export TRELLO_BOARD_ID="..."
export DISCORD_WEBHOOK_URL="..."
export DISCORD_MEMBER_MAP="..."   # optional
```

Then run:

```bash
uv run trello_discord_notifier.py
```

The first run only seeds state and won't notify on the board's pre-existing history — that's expected.

## 7. Done

The workflow in `.github/workflows/notify.yml` runs automatically every 5 minutes. You can also trigger it manually from the **Actions** tab → "Trello Discord Notifier" → **Run workflow**, useful for testing.

## Notes / limitations

- Timezone defaults to `Asia/Manila` — change `TZ_NAME` in `notify.yml` if needed.
- If a card's due date changes, its reminder history isn't reset (rare edge case) — delete the card's entry from `state.json` manually if you need to re-trigger a reminder.
- GitHub's schedule can run a few minutes late during high load; the 20-minute firing window in the script absorbs that.
- Only cards with a due date set and not marked complete are checked for due-date reminders.
- Board-activity notifications fire for every member's actions, including your own.

## Real-time on Railway

Instead of polling every 5 minutes, `app.py` runs a small always-on server that Trello calls the instant something happens on the board (via a registered webhook), so board-activity notifications land within seconds. Due-date reminders still can't be pushed by Trello (nothing "happens" when a deadline approaches), so those are checked on an in-process 1-minute interval instead.

### 1. Create a new Railway service

1. In your Railway project, **New → Deploy from GitHub repo** and pick this repo.
2. Railway auto-detects the Python project via `pyproject.toml`/`uv.lock` and uses the `Procfile`'s `web:` command to start it.

### 2. Add a volume for state.json

State needs to persist across redeploys/restarts (Railway's default filesystem doesn't guarantee that):

1. In the service → **Volumes → New Volume**, mount it at e.g. `/data`.
2. Add an env var `STATE_FILE=/data/state.json`.

### 3. Set environment variables

In the service's **Variables** tab, add the same variables as the GitHub Actions setup, plus one new one:

- `TRELLO_KEY`
- `TRELLO_TOKEN`
- `TRELLO_BOARD_ID`
- `DISCORD_WEBHOOK_URL`
- `DISCORD_MEMBER_MAP` (optional)
- `STATE_FILE=/data/state.json` (from step 2)
- `PORT` — Railway sets this automatically; the `Procfile` already reads it.

### 4. Deploy, then register the Trello webhook

1. Deploy the service and copy its public URL from Railway (Settings → Networking → Generate Domain if you don't have one yet).
2. Locally, with the same env vars loaded (`TRELLO_KEY`, `TRELLO_TOKEN`, `TRELLO_BOARD_ID`), run:
   ```bash
   uv run register_webhook.py https://<your-railway-domain>/trello-webhook
   ```
   Trello will `HEAD` that URL to verify it's reachable before registering — the server already handles that at `/trello-webhook`.
3. Confirm it worked: `uv run register_webhook.py --list` should show your webhook as `active`.

From here, creating/moving/commenting on cards notifies Discord within seconds. To remove the webhook later: `uv run register_webhook.py --delete <webhook-id>`.

### Notes

- The webhook server and the GitHub Actions workflow both write to the same `state.json` shape but aren't meant to run simultaneously against the same board — pick one.
- **Dedup works differently between the two.** The GitHub Actions (polling) path tracks an Action Cursor in `state.json` — the id of the last Trello Action it processed — so re-running never double-notifies. The Railway (webhook) path has no cursor at all; it trusts Trello's webhook delivery to call the server once per action. Trello's webhook delivery is reliable but not perfectly guaranteed (occasional retries/drops) — acceptable for a notification use case, but not a system of record. Under a webhook-only deployment, `state.json`'s `action_cursor` and `self_member_id` fields are simply never populated — that's expected, not a bug.
