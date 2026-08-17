# Trello → Discord Notifier

Sends you a Discord message when things worth noticing happen on your Trello board.

**Due-date reminders**, for cards with a due date set and not marked complete:

- 1 day before, at 8:00 AM
- Same day, at 8:00 AM (skipped if the deadline itself is before 8am)
- 30 minutes before the due time

**Board activity**, for any member's action on the board:

- 🆕 Card created
- ➡️ Card moved between lists
- 💬 Comment added

Runs for free forever via GitHub Actions (no server needed).

## 1. Create a Discord webhook

1. In Discord, go to the channel you want notifications in → **Edit Channel → Integrations → Webhooks → New Webhook**.
2. Give it a name/avatar if you like, then click **Copy Webhook URL**. This is `DISCORD_WEBHOOK_URL`.

## 2. Get Trello credentials

1. Go to [trello.com/power-ups/admin](https://trello.com/power-ups/admin/) (or [trello.com/app-key](https://trello.com/app-key)) while logged in, and click **New** to create an app if you don't have one yet — copy its **API Key**. This is `TRELLO_KEY`.
2. On the same page, click the link to manually generate a **Token** (grants read access) → copy it. This is `TRELLO_TOKEN`.
3. Get your board ID: open your board in the browser and grab the ID from the URL (the string after `/b/`), e.g. `trello.com/b/AbCd1234/my-board` → `AbCd1234`. This is `TRELLO_BOARD_ID`.

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

If a card has assigned Trello members, board-activity messages can `@mention` them in Discord instead of just printing their Trello name. This requires mapping each Trello member's id to their Discord user id, since the two platforms have no built-in link.

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
