#!/usr/bin/env bash
# Operational monitoring for the test phase: push a notification on business
# events. Currently: a new tester signed up. This is deliberately separate from
# healthcheck.sh — it is about "what happened?", not "is the service healthy?".
#
# Polls the DB each tick and pushes when the user count grows. Up to one tick of
# latency; a real-time push from the app would be the production approach.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/.events.log"
# Repo: ../_common.sh. Staged flat by install.sh, which sets YARA_COMMON.
# shellcheck source=scripts/monitoring/_common.sh
source "${YARA_COMMON:-$SCRIPT_DIR/../_common.sh}"

USERS_STATE="$SCRIPT_DIR/.events.users_state"

check_new_users() {
  local count prev=0
  count="$(_compose exec -T db psql -U yara -t -A -c 'select count(*) from users' 2>/dev/null | tr -d '[:space:]')"
  [[ "$count" =~ ^[0-9]+$ ]] || { log "new-users: db unreachable"; return; }
  [[ -f "$USERS_STATE" ]] && prev="$(cat "$USERS_STATE")"
  # prev>0 guard so the first run seeds the baseline instead of announcing every
  # existing user at once.
  if [[ "$prev" =~ ^[0-9]+$ && "$prev" -gt 0 && "$count" -gt "$prev" ]]; then
    local newest delta=$((count - prev))
    newest="$(_compose exec -T db psql -U yara -t -A -c \
      "select coalesce(nullif(phone_number,''),'(geen nummer)')||' · '||coalesce(preferred_language,'?')||' · '||coalesce(municipality,'?') from users order by created_at desc limit 1" \
      2>/dev/null | tr -d '\r' | xargs)"
    notify "Yara: nieuwe gebruiker 🎉" "Testers: $prev → $count (+$delta). Nieuwste: ${newest:-onbekend}" "default" "tada"
  fi
  echo "$count" >"$USERS_STATE"
}

main() {
  log "--- events tick ---"
  check_new_users
}

main
