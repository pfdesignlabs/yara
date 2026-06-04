# Monitoring

Tooling to keep an eye on the local Yara stack during the test phase.

```
monitoring/
  analyze.py          # manual analysis CLI — inspect the operational data
  _common.sh          # shared ntfy / env / log helpers
  install.sh          # installs both launchd agents (idempotent)
  watchdog/
    healthcheck.sh    # health  -> com.yara.watchdog  (auto-heal + functional checks)
  events/
    notify_events.sh  # operational -> com.yara.events (push on new tester)
```

Two distinct concerns, deliberately split:

- **health** (`watchdog/`) — *is the service up and working?* Auto-heals the
  Docker daemon, containers, and `app`; runs functional checks `/health` can't
  see (OpenAI canary, Twilio balance, app-error scan); alerts (never restarts)
  on ngrok.
- **operational** (`events/`) — *what happened?* Pushes when a new tester signs
  up. Polls every tick; a real-time push from the app is the production approach
  (see [BACKLOG.md](../../BACKLOG.md), *Ops / monitoring*).

Both alert via [ntfy.sh](https://ntfy.sh) — a channel independent of the
monitored stack, so the push lands even when app/ngrok is down.

## analyze.py (manual)

```bash
.venv/bin/python scripts/monitoring/analyze.py                  # snapshot
.venv/bin/python scripts/monitoring/analyze.py --user +316XXXXXXXX  # drill-down (+ LLM eval)
```

## Watchdog + events agents (automated)

Set a private ntfy topic in `.env` (`NTFY_TOPIC=…`), subscribe to it in the ntfy
app, then install both launchd agents (re-run after changing the scripts or the
relevant `.env` values):

```bash
bash scripts/monitoring/install.sh
# uninstall:
launchctl unload ~/Library/LaunchAgents/com.yara.{watchdog,events}.plist \
  && rm ~/Library/LaunchAgents/com.yara.{watchdog,events}.plist
```

The installer copies the scripts out of `~/Documents` and stages the secrets
they need, because macOS TCC blocks launchd from running or reading files there.
This is a test-phase stopgap (single host, runs only while this Mac is awake).
