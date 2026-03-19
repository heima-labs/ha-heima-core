#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=/dev/null
[[ -f "$REPO_ROOT/scripts/.env" ]] && source "$REPO_ROOT/scripts/.env"

HA_URL="${HA_URL:-http://127.0.0.1:8823}"
HA_TOKEN="${HA_TOKEN:-}"
DEV_CONTAINER_NAME="${DEV_CONTAINER_NAME:-homeassistant-test}"
STORAGE_DIR="$REPO_ROOT/docs/examples/ha_test_instance/docker/ha_config/.storage"

echo "Generating learning fixture storage..."
python3 "$REPO_ROOT/scripts/generate_learning_fixtures.py" --storage-dir "$STORAGE_DIR"

echo "Copying fixture storage into container '$DEV_CONTAINER_NAME'..."
docker cp "$STORAGE_DIR/heima_pattern_events" "$DEV_CONTAINER_NAME:/config/.storage/heima_pattern_events"
docker cp "$STORAGE_DIR/heima_proposals" "$DEV_CONTAINER_NAME:/config/.storage/heima_proposals"

echo "Restarting Home Assistant lab container..."
docker restart "$DEV_CONTAINER_NAME" >/dev/null

echo "Waiting for Home Assistant to come back on $HA_URL ..."
deadline=$((SECONDS + 180))
until curl -fsS "$HA_URL/" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "FAIL: Home Assistant did not become reachable at $HA_URL after restore" >&2
    exit 1
  fi
  sleep 2
done

if [[ -n "$HA_TOKEN" ]]; then
  echo "Waiting for Heima entities to be available..."
  deadline=$((SECONDS + 180))
  until curl -fsS \
    -H "Authorization: Bearer ${HA_TOKEN}" \
    "$HA_URL/api/states/sensor.heima_house_state" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "FAIL: Heima entities did not become ready after restore" >&2
      exit 1
    fi
    sleep 2
  done
fi

echo "PASS: learning fixtures restored and Home Assistant reachable"
