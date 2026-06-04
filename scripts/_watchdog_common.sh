# Shared infra for the watchdog scripts (healthcheck.sh, notify_events.sh).
# Source this AFTER setting SCRIPT_DIR and LOG_FILE. Not meant to run on its own.
#
# Runs from launchd, which provides a bare PATH and cannot read ~/Documents
# (macOS TCC). docker CLI has its own grant so compose works; secrets come from a
# staged env file outside ~/Documents (see install-watchdog.sh). The repo path
# and that env file are passed in via YARA_PROJECT_DIR / YARA_WATCHDOG_ENV.

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

PROJECT_DIR="${YARA_PROJECT_DIR:-$(dirname "$SCRIPT_DIR")}"
ENV_FILE="${YARA_WATCHDOG_ENV:-$PROJECT_DIR/.env}"
NTFY_SERVER="https://ntfy.sh"

_env() {
  [[ -f "$ENV_FILE" ]] || return 0
  grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2-
}

NTFY_TOPIC="$(_env NTFY_TOPIC)"
_ntfy_server_override="$(_env NTFY_SERVER)"
[[ -n "$_ntfy_server_override" ]] && NTFY_SERVER="$_ntfy_server_override"

log() {
  printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" | tee -a "$LOG_FILE"
}

notify() {
  local title="$1" body="$2" priority="${3:-default}" tags="${4:-warning}"
  log "ntfy[$title] $body"
  if [[ -z "$NTFY_TOPIC" ]]; then
    log "(ntfy skipped: NTFY_TOPIC not set in $ENV_FILE)"
    return
  fi
  curl -fsS -H "Title: $title" -H "Priority: $priority" -H "Tags: $tags" \
    -d "$body" "$NTFY_SERVER/$NTFY_TOPIC" >/dev/null 2>&1 || log "(ntfy send failed)"
}

# Alert only on state changes so a persistent fault does not re-alert every tick.
_alert_transition() {
  local state_file="$1" now="$2" down_msg="$3" up_msg="$4"
  local prev="up"
  [[ -f "$state_file" ]] && prev="$(cat "$state_file")"
  if [[ "$now" == "down" && "$prev" == "up" ]]; then
    notify "Yara watchdog" "$down_msg" "urgent" "rotating_light"
  elif [[ "$now" == "up" && "$prev" == "down" ]]; then
    notify "Yara watchdog" "$up_msg" "high" "white_check_mark"
  fi
  echo "$now" >"$state_file"
}

_compose() {
  (cd "$PROJECT_DIR" && docker compose "$@")
}
