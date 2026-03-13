#!/usr/bin/env bash
set -euo pipefail

# Backward-compatible wrapper that delegates to the canonical Python live test.

HA_URL="${HA_URL:-http://homeassistant.local:8123}"
HA_TOKEN="${HA_TOKEN:-}"
TIMEOUT_S="${TIMEOUT_S:-45}"
POLL_S="${POLL_S:-1}"

usage() {
  cat <<'EOF'
Usage:
  HA_TOKEN=<token> scripts/test_heima_live.sh [--ha-url URL] [--timeout-s N] [--poll-s N]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ha-url)
      HA_URL="${2:-}"; shift 2;;
    --timeout-s)
      TIMEOUT_S="${2:-}"; shift 2;;
    --poll-s)
      POLL_S="${2:-}"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2;;
  esac
done

if [[ -z "$HA_TOKEN" ]]; then
  echo "HA_TOKEN is required" >&2
  exit 2
fi

exec ./scripts/live_tests/000_live_smoke.py \
  --ha-url "$HA_URL" \
  --ha-token "$HA_TOKEN" \
  --timeout-s "$TIMEOUT_S" \
  --poll-s "$POLL_S"
