# Trello-Discord Notifier

Watches a single Trello board and sends Discord messages when things worth noticing happen on it — deadlines approaching and board activity occurring.

## Language

**Event Type**:
One of an explicit, enumerated set of things this system notifies on: due-soon, card moved, card created, comment added. Deliberately not a generic mirror of Trello's full activity feed — each type is chosen for signal, not completeness.
_Avoid_: Notification type, trigger

**Computed Event**:
An Event Type derived from card state plus wall-clock time, with no backing entry in Trello's action log — currently only the due-soon reminder, which fires when a card's due date crosses a checkpoint we calculate. Deduped via our own checkpoint keys in `state.json`.
_Avoid_: Synthetic event, derived event

**Logged Event**:
An Event Type sourced directly from a Trello Action returned by the Actions API — e.g. card moved, card created, comment added. Deduped using Trello's own Action `id`. Every Logged Event has an actor (the Trello member who caused it), notified regardless of who that actor is.
_Avoid_: Native event, action event

**Checkpoint**:
A specific point in time, relative to a card's due date, at which a due-soon Computed Event may fire: 1 day before at 8am, same day at 8am, or 30 minutes before. Each checkpoint fires at most once per card.
_Avoid_: Reminder time, trigger time

**Firing Window**:
The span of time (currently 20 minutes) after a checkpoint's target time during which it is still eligible to fire, absorbing scheduler lateness.
_Avoid_: Grace period, buffer

**Action Cursor**:
The board-wide "last processed Trello Action" position (id/timestamp) used to dedup Logged Events across runs. A single value per board, independent of any card's lifecycle — unlike checkpoint state, it needs no pruning when cards are archived or completed, since it tracks a stream position rather than per-card flags. Populated and consumed only by the polling adapter (`run()`/`_process_logged_events()`); the webhook adapter never reads or writes it, relying instead on Trello's webhook delivery as its dedup boundary. Under a webhook-only deployment, `state.json`'s `action_cursor` field is simply never populated — expected, not a bug.
_Avoid_: Last seen id, watermark

**Member Map**:
A configured lookup from Trello member id to Discord user id (`DISCORD_MEMBER_MAP`), used to turn a card's assigned members into real Discord `@mentions` on Logged Event messages. Trello and Discord identities have no built-in link, so this mapping is maintained by hand. An assignee absent from the map still appears in the message, using their Trello name instead of a mention.
_Avoid_: User mapping, mention config
