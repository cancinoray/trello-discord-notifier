# Trello → Discord Deadline Notifier

Sends you a Discord message for cards with due dates:
- 1 day before, at 8:00 AM
- Same day, at 8:00 AM (skipped if the deadline itself is before 8am)
- 30 minutes before the due time

Runs for free forever via GitHub Actions (no server needed).

## 1. Create a Discord webhook
1. In Discord, go to the channel you want notifications in → **Edit Channel → Integrations → Webhooks → New Webhook**.
2. Give it a name/avatar if you like, then click **Copy Webhook URL**. This is `DISCORD_WEBHOOK_URL`.

## 2. Get Trello credentials
1. Go to https://trello.com/power-ups/admin/ (or https://trello.com/app-key) while logged in — copy your **API Key**. This is `TRELLO_KEY`.
2. On the same page, click the link to manually generate a **Token** (grants read access) → copy it. This is `TRELLO_TOKEN`.
3. Get your board ID: open your board in the browser, add `.json` to the end of the URL, or simply grab the ID from the URL itself (the string after `/b/`). This is `TRELLO_BOARD_ID`.

## 3. Push this project to GitHub
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

## 4. Add your secrets
In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**. Add all four:
- `TRELLO_KEY`
- `TRELLO_TOKEN`
- `TRELLO_BOARD_ID`
- `DISCORD_WEBHOOK_URL`

## 5. Done
The workflow in `.github/workflows/notify.yml` runs automatically every 15 minutes. You can also trigger it manually from the **Actions** tab → "Trello Discord Notifier" → **Run workflow**, useful for testing.

## Notes / limitations
- Timezone defaults to `Asia/Manila` — change `TZ_NAME` in `notify.yml` if needed.
- If a card's due date changes, its reminder history isn't reset (rare edge case) — delete the card's entry from `state.json` manually if you need to re-trigger a reminder.
- GitHub's schedule can run a few minutes late during high load; the 20-minute firing window in the script absorbs that.
- Only cards with a due date set and not marked complete are checked.
