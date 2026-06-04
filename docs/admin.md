# Admin / operator guide

Running and operating Yara in the test phase. For how the system works
internally, see [architecture.md](architecture.md); for setup from scratch, see
the README.

## Run the stack

```bash
docker compose up -d            # app (:8000) + db (:5432)
docker compose exec app alembic upgrade head   # apply migrations
curl http://localhost:8000/health              # → {"status":"ok"}
```

Config lives in `.env` (gitignored): `DATABASE_URL`, `OPENAI_API_KEY`,
`TWILIO_*`, `POSTGRES_*`, and `NTFY_TOPIC` for monitoring alerts.

## Expose the webhook

Twilio must reach the app over a public URL:

```bash
ngrok http 8000
```

Point the Twilio WhatsApp Sandbox inbound webhook at
`https://<ngrok-domain>/webhooks/twilio/whatsapp`. If the ngrok URL changes,
update it in the Twilio console — otherwise inbound messages silently stop.

## Monitoring

Two launchd agents watch the stack and push to your phone via
[ntfy.sh](https://ntfy.sh) (install once with `scripts/monitoring/install.sh`;
see [scripts/monitoring/README.md](../scripts/monitoring/README.md)):

- **`com.yara.watchdog`** — auto-heals Docker/containers/app, runs functional
  checks (OpenAI canary, Twilio balance, app-error scan), alerts on ngrok.
- **`com.yara.events`** — pushes when a new tester signs up.

Logs: `~/Library/Application Support/yara/com.yara.{watchdog,events}.launchd.log`.

Inspect activity by hand:

```bash
.venv/bin/python scripts/monitoring/analyze.py                  # snapshot
.venv/bin/python scripts/monitoring/analyze.py --user +316XXXXXXXX  # drill-down + LLM eval
```

## Database

- Connect with a GUI (TablePlus): `localhost:5432`, user/pass/db = `yara`.
- Migrations: `docker compose exec app alembic upgrade head`.
- Conversation history is the source of truth — to debug a conversation, read
  the `message` rows (with `source_node`) for that user.

## Reminders

APScheduler ticks every minute and sends due reminders via Twilio. A reminder
with `status=scheduled` and a past `scheduled_for` fires on the next tick; check
pending ones in the `analyze.py` snapshot.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Webhook unreachable, no inbound | ngrok down or URL changed | restart ngrok; update the Twilio webhook URL |
| `/health` ok but bot doesn't reply | OpenAI balance/key, or Twilio balance | watchdog's canary/balance check will alert; top up / fix the key |
| Nothing runs after a reboot | Docker Desktop not started | `open -a Docker`, then `docker compose up -d` (watchdog auto-heals this) |
| App errors in a conversation | exception in a node | router returns the `fallbacks.llm_error` reply; check `docker compose logs app` |
| Empty/nameless user appears | a webhook POST without a `From` (e.g. a probe) created a ghost row | known gap — Twilio signature validation is on the BACKLOG; safe to delete the row |
| Reminder logged but not sent | reminder has no `conversation_id` | known limitation (see BACKLOG); dispatcher skips these |

## Safety rails

- `.env` and `workspace/` are gitignored and **must never be committed** (this
  repo is public; `workspace/` holds tender/business docs + third-party
  reports). `.dockerignore` keeps them out of any image build too.
- Uploaded documents are sensitive PII on local disk
  (`storage/uploads/`) — see the GDPR/security item on the BACKLOG before any
  non-test use.
