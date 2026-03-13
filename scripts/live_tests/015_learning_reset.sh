#!/usr/bin/env bash
set -euo pipefail

HA_URL="${HA_URL:-http://127.0.0.1:8123}"
HA_TOKEN="${HA_TOKEN:-}"

if [[ -z "$HA_TOKEN" ]]; then
  echo "FAIL: HA_TOKEN is required for 015_learning_reset.sh" >&2
  exit 2
fi

echo "Resetting Heima learning baseline..."
curl -fsS -X POST \
  -H "Authorization: Bearer ${HA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"command":"learning_reset"}' \
  "${HA_URL%/}/api/services/heima/command" >/dev/null

echo "PASS: learning baseline reset"

