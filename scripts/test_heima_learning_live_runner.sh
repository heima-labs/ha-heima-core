#!/usr/bin/env bash
set -euo pipefail

# Load local env overrides if present (not committed)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

HA_URL="${HA_URL:-http://127.0.0.1:8123}"
HA_TOKEN="${HA_TOKEN:-}"
PERSON_SLUG="${PERSON_SLUG:-}"

usage() {
  cat <<'EOF'
Usage:
  HA_TOKEN=<token> PERSON_SLUG=<slug> ./scripts/test_heima_learning_live_runner.sh [--ha-url URL]

Options:
  --ha-url URL   Home Assistant base URL (default: $HA_URL or http://127.0.0.1:8123)

This runner:
1) Resets Heima learning data via `heima.command` -> `learning_reset`
2) Executes scripts/live_tests/020_learning_pipeline.py with the provided person slug
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ha-url)
      HA_URL="$2"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2;;
  esac
done

if [[ -z "$HA_TOKEN" ]]; then
  echo "HA_TOKEN is required" >&2
  exit 2
fi
if [[ -z "$PERSON_SLUG" ]]; then
  echo "PERSON_SLUG is required" >&2
  exit 2
fi

echo "Resetting learning data..."
curl -fsS -X POST \
  -H "Authorization: Bearer ${HA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"command":"learning_reset"}' \
  "${HA_URL%/}/api/services/heima/command" >/dev/null

echo "Running learning live E2E..."
./scripts/live_tests/020_learning_pipeline.py \
  --ha-url "${HA_URL}" \
  --ha-token "${HA_TOKEN}" \
  --person-slug "${PERSON_SLUG}"
