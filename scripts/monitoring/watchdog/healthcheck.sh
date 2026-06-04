#!/usr/bin/env bash
# Test-phase health watchdog for the local Yara stack.
#
# Two kinds of checks:
#   - infra ("is it up?"):          Docker daemon, containers, /health, ngrok
#   - functional ("does it work?"): OpenAI canary + log-scan, Twilio balance,
#                                   app errors in the logs
# Operational/business signals (e.g. a new tester signed up) live in
# notify_events.sh — this script is strictly about service health.
#
# Auto-heals what is safe to restart (Docker daemon, containers, app). ngrok is
# NOT restarted: a restart hands out a new public URL that would silently break
# the Twilio webhook, so on ngrok failure we only alert.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/.watchdog.log"
# Repo: ../_common.sh. Staged flat by install.sh, which sets YARA_COMMON.
# shellcheck source=scripts/monitoring/_common.sh
source "${YARA_COMMON:-$SCRIPT_DIR/../_common.sh}"

NGROK_STATE="$SCRIPT_DIR/.watchdog.ngrok_state"
OPENAI_STATE="$SCRIPT_DIR/.watchdog.openai_state"
TWILIO_STATE="$SCRIPT_DIR/.watchdog.twilio_state"
ERR_SIG="$SCRIPT_DIR/.watchdog.err_sig"

HEALTH_URL="http://localhost:8000/health"
NGROK_API="http://localhost:4040/api/tunnels"
TWILIO_MIN_BALANCE=5
CANARY_MODEL="gpt-4o-mini"

_docker_ready() {
  docker info >/dev/null 2>&1
}

heal_docker() {
  _docker_ready && return 0
  log "Docker daemon down — starting Docker Desktop"
  open -a Docker
  for _ in $(seq 1 60); do
    if _docker_ready; then
      notify "Yara watchdog" "Docker was down — restarted Docker Desktop" "high" "wrench"
      return 0
    fi
    sleep 5
  done
  notify "Yara watchdog" "Docker did not come up within 5 min — manual check needed" "urgent" "rotating_light"
  return 1
}

heal_containers() {
  local down=()
  for svc in db app; do
    [[ "$(_compose ps --status running --services 2>/dev/null | grep -c "^$svc$")" == "1" ]] || down+=("$svc")
  done
  [[ ${#down[@]} -eq 0 ]] && return 0
  log "Containers down: ${down[*]} — running docker compose up -d"
  _compose up -d >/dev/null 2>&1
  sleep 5
  notify "Yara watchdog" "Restarted container(s): ${down[*]}" "high" "wrench"
}

_health_code() {
  curl -fsS -o /dev/null -w '%{http_code}' --max-time 10 "$HEALTH_URL" 2>/dev/null
}

# Poll /health for up to ~30s before deciding the app is dead — a container that
# heal_containers just (re)started needs a moment to finish booting.
_await_health() {
  local code
  for _ in $(seq 1 6); do
    code="$(_health_code)"
    [[ "$code" == "200" ]] && return 0
    sleep 5
  done
  echo "$code"
  return 1
}

heal_app() {
  _await_health >/dev/null && return 0
  log "Health check failing — restarting app"
  _compose restart app >/dev/null 2>&1
  if _await_health >/dev/null; then
    notify "Yara watchdog" "App /health was failing — restarted, now 200" "high" "wrench"
  else
    notify "Yara watchdog" "App /health still '$(_health_code)' after restart — manual check needed" "urgent" "rotating_light"
  fi
}

# ngrok is test-only: alert on state changes, never restart.
check_ngrok() {
  local public_url now="down"
  public_url="$(curl -fsS --max-time 5 "$NGROK_API" 2>/dev/null \
    | grep -oE '"public_url":"https://[^"]+"' | head -1 | sed -E 's/.*"(https:[^"]+)"/\1/')"
  if [[ -n "$public_url" ]]; then
    local code
    code="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 10 \
      -H "ngrok-skip-browser-warning: 1" "$public_url/health" 2>/dev/null)"
    [[ "$code" == "200" ]] && now="up"
  fi
  _alert_transition "$NGROK_STATE" "$now" \
    "ngrok tunnel is DOWN — public webhook unreachable. Restart ngrok and check the Twilio webhook URL." \
    "ngrok tunnel is back up: $public_url"
  log "ngrok: $now${public_url:+ ($public_url)}"
}

# Proactive canary: a 1-token call that fails fast if the key is invalid or the
# account is out of quota/credit, before a real tester hits it.
check_openai() {
  local key
  key="$(_env OPENAI_API_KEY)"
  [[ -z "$key" ]] && { log "openai: skipped (no key)"; return; }
  local out="/tmp/yara_openai_canary.json" code
  code="$(curl -fsS -o "$out" -w '%{http_code}' --max-time 15 \
    https://api.openai.com/v1/chat/completions \
    -H "Authorization: Bearer $key" -H 'Content-Type: application/json' \
    -d "{\"model\":\"$CANARY_MODEL\",\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}]}" \
    2>/dev/null)"
  if [[ "$code" == "200" ]]; then
    _alert_transition "$OPENAI_STATE" "up" "" "OpenAI werkt weer."
    log "openai canary: 200"
  else
    local reason
    reason="$(grep -oE '"(message|code)": *"[^"]+"' "$out" 2>/dev/null | head -2 | tr '\n' ' ')"
    _alert_transition "$OPENAI_STATE" "down" \
      "OpenAI-canary faalt (HTTP $code). ${reason:-Mogelijk saldo/quota op of sleutel ongeldig.}" \
      "OpenAI werkt weer."
    log "openai canary: $code $reason"
  fi
}

check_twilio_balance() {
  local sid token
  sid="$(_env TWILIO_ACCOUNT_SID)"
  token="$(_env TWILIO_AUTH_TOKEN)"
  [[ -z "$sid" || -z "$token" ]] && { log "twilio: skipped (no creds)"; return; }
  local resp balance currency
  resp="$(curl -fsS --max-time 10 -u "$sid:$token" \
    "https://api.twilio.com/2010-04-01/Accounts/$sid/Balance.json" 2>/dev/null)"
  balance="$(printf '%s' "$resp" | grep -oE '"balance" *: *"[^"]+"' | grep -oE '[0-9]+(\.[0-9]+)?')"
  currency="$(printf '%s' "$resp" | grep -oE '"currency" *: *"[^"]+"' | sed -E 's/.*"([A-Z]+)".*/\1/')"
  [[ -z "$balance" ]] && { log "twilio balance: unreadable"; return; }
  log "twilio balance: $balance $currency"
  if awk "BEGIN{exit !($balance < $TWILIO_MIN_BALANCE)}"; then
    _alert_transition "$TWILIO_STATE" "down" \
      "Twilio-saldo laag: $balance $currency (drempel $TWILIO_MIN_BALANCE). Bot kan straks niet meer antwoorden." \
      "Twilio-saldo weer op peil: $balance $currency."
  else
    _alert_transition "$TWILIO_STATE" "up" "" "Twilio-saldo weer op peil: $balance $currency."
  fi
}

# Scan recent logs for tracebacks and OpenAI 4xx/5xx; dedup on content so the
# same error does not re-alert every tick.
check_app_errors() {
  local hits sig prev=""
  hits="$(_compose logs --no-color --since 6m app 2>/dev/null \
    | grep -iE 'Traceback|ERROR:|Exception|api\.openai\.com.*"HTTP/[0-9.]+ (4|5)[0-9][0-9]' \
    | tail -10)"
  if [[ -z "$hits" ]]; then
    : >"$ERR_SIG"
    return
  fi
  sig="$(printf '%s' "$hits" | shasum | cut -d' ' -f1)"
  [[ -f "$ERR_SIG" ]] && prev="$(cat "$ERR_SIG")"
  if [[ "$sig" != "$prev" ]]; then
    notify "Yara: app-fouten" "Nieuwe fouten in de app-log (laatste 6 min):"$'\n'"$(printf '%s' "$hits" | tail -3)" "high" "boom"
    echo "$sig" >"$ERR_SIG"
  fi
}

main() {
  log "--- watchdog tick ---"
  heal_docker || return
  heal_containers
  heal_app
  check_ngrok
  check_openai
  check_twilio_balance
  check_app_errors
}

main
