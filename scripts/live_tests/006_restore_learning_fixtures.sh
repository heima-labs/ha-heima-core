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
DOCKER_BIN="${DOCKER_BIN:-}"

if [[ -z "$DOCKER_BIN" ]]; then
  if command -v docker >/dev/null 2>&1; then
    DOCKER_BIN="$(command -v docker)"
  elif [[ -x "/Applications/Docker.app/Contents/Resources/bin/docker" ]]; then
    DOCKER_BIN="/Applications/Docker.app/Contents/Resources/bin/docker"
  else
    echo "FAIL: docker binary not found; set DOCKER_BIN or ensure docker is on PATH" >&2
    exit 1
  fi
fi

echo "Stopping Home Assistant lab container '$DEV_CONTAINER_NAME' before fixture restore..."
"$DOCKER_BIN" stop "$DEV_CONTAINER_NAME" >/dev/null

echo "Generating learning fixture storage..."
python3 "$REPO_ROOT/scripts/generate_learning_fixtures.py" --storage-dir "$STORAGE_DIR"

echo "Using host-mounted fixture storage at '$STORAGE_DIR'..."
echo "Skipping docker cp because /config is bind-mounted from the host in the test lab."

echo "Starting Home Assistant lab container..."
"$DOCKER_BIN" start "$DEV_CONTAINER_NAME" >/dev/null

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

  echo "Refreshing room area assignments and room config after restart..."
  python3 "$REPO_ROOT/scripts/recover_test_lab_config.py" \
    --ha-url "$HA_URL" \
    --ha-token "$HA_TOKEN" \
    --section rooms

  echo "Refreshing learning signal config after restart..."
  python3 "$REPO_ROOT/scripts/recover_test_lab_config.py" \
    --ha-url "$HA_URL" \
    --ha-token "$HA_TOKEN" \
    --section learning

  echo "Waiting for restored learning baseline to load into diagnostics..."
  deadline=$((SECONDS + 180))
  until python3 - "$HA_URL" "$HA_TOKEN" <<'PY'
import json
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")
token = sys.argv[2]

headers = {"Authorization": f"Bearer {token}"}

def fetch_json(path: str):
    req = urllib.request.Request(f"{base_url}{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())

entry_id = ""
for item in fetch_json("/api/config/config_entries/entry"):
    if str(item.get("domain") or "") == "heima":
        entry_id = str(item.get("entry_id") or "")
        if entry_id:
            break

if not entry_id:
    raise SystemExit(1)

diag = fetch_json(f"/api/diagnostics/config_entry/{entry_id}")
runtime = ((diag.get("data") or {}).get("runtime") or {})
event_store = runtime.get("event_store") or {}
by_type = event_store.get("by_type") or {}

try:
    lighting = int(float(str(by_type.get("lighting") or "0")))
except ValueError:
    lighting = 0

raise SystemExit(0 if lighting >= 84 else 1)
PY
  do
    if (( SECONDS >= deadline )); then
      echo "FAIL: restored lighting baseline did not load into diagnostics" >&2
      exit 1
    fi
    sleep 2
  done
fi

echo "PASS: learning fixtures restored and Home Assistant reachable"
