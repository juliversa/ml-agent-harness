#!/bin/bash
# Notification (optional, RULES R30): kit/notify.sh "<title>" "<message>". Sent only when NTFY_TOPIC is set (ntfy.sh or $NTFY_URL); else nothing.
# Used by kit/keeper.py; the keeper's own record is <comp>/keeper.md either way. Never fails the caller.
[ -n "${NTFY_TOPIC:-}" ] || exit 0
curl -s -m 15 -H "Title: $1" -d "$2" "${NTFY_URL:-https://ntfy.sh}/$NTFY_TOPIC" >/dev/null || true
