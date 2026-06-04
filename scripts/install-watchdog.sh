#!/usr/bin/env bash
# Install (or refresh) the test-phase monitoring as two launchd agents:
#   com.yara.watchdog  -> healthcheck.sh   (service health, auto-heal)
#   com.yara.events    -> notify_events.sh (operational: new testers)
#
# Why not just point launchd at scripts/*.sh in the repo:
# macOS TCC blocks launchd from executing scripts in ~/Documents and from
# reading files there with plain tools. So we copy the scripts outside
# ~/Documents and stage the secrets they need (read here from the repo .env —
# Terminal is allowed to read ~/Documents — into a chmod 600 file next to them).
# docker compose still works under launchd because Docker has its own grant.
#
# Re-run this after changing the scripts or the relevant .env values.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="$HOME/Library/Application Support/yara"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
ENV_OUT="$INSTALL_DIR/watchdog.env"

mkdir -p "$INSTALL_DIR"
for f in _watchdog_common.sh healthcheck.sh notify_events.sh; do
  cp "$REPO/scripts/$f" "$INSTALL_DIR/$f"
done
chmod +x "$INSTALL_DIR/healthcheck.sh" "$INSTALL_DIR/notify_events.sh"

: >"$ENV_OUT"
chmod 600 "$ENV_OUT"
for key in NTFY_TOPIC NTFY_SERVER OPENAI_API_KEY TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN; do
  line="$(grep -E "^$key=" "$REPO/.env" 2>/dev/null | tail -1 || true)"
  [[ -n "$line" ]] && printf '%s\n' "$line" >>"$ENV_OUT"
done

# _install_agent <label> <script> <interval-seconds>
_install_agent() {
  local label="$1" script="$2" interval="$3"
  local plist="$LAUNCH_AGENTS/$label.plist"
  cat >"$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$label</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$INSTALL_DIR/$script</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>YARA_PROJECT_DIR</key>
        <string>$REPO</string>
        <key>YARA_WATCHDOG_ENV</key>
        <string>$ENV_OUT</string>
    </dict>
    <key>StartInterval</key>
    <integer>$interval</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/$label.launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/$label.launchd.log</string>
</dict>
</plist>
PLIST
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load "$plist"
  echo "  $label -> $script (every ${interval}s): $(launchctl list | grep "$label" || echo 'NOT loaded')"
}

echo "Staged to $INSTALL_DIR ($(wc -l <"$ENV_OUT" | tr -d ' ') secrets in watchdog.env, chmod 600)"
echo "Agents:"
_install_agent com.yara.watchdog healthcheck.sh 300
_install_agent com.yara.events notify_events.sh 300
echo
echo "Logs:      $INSTALL_DIR/com.yara.{watchdog,events}.launchd.log"
echo "Uninstall: launchctl unload $LAUNCH_AGENTS/com.yara.{watchdog,events}.plist && rm $LAUNCH_AGENTS/com.yara.{watchdog,events}.plist"
