#!/usr/bin/env bash
set -euo pipefail

# Apply a JSON merge patch to the Heima config entry options on HA-dev.
#
# Default target:
#   $REMOTE_HOST:$REMOTE_BASE
#
# Default container:
#   homeassistant-dev

REMOTE_HOST="${REMOTE_HOST:-user@ha-host}"
REMOTE_BASE="${REMOTE_BASE:-HA/HA-dev}"
CONTAINER_NAME="${CONTAINER_NAME:-homeassistant-dev}"
PATCH_FILE_LOCAL="${PATCH_FILE_LOCAL:-docs/examples/ha_test_instance/heima_dev_options_patch.json}"
PATCH_FILE_REMOTE_NAME="heima_dev_options_patch.json"
CONFIG_ENTRIES_PATH=".storage/core.config_entries"

usage() {
  cat <<'EOF'
Usage:
  scripts/patch_heima_dev_options.sh [--dry-run]

Environment overrides:
  REMOTE_HOST=user@ha-host
  REMOTE_BASE=HA/HA-dev
  CONTAINER_NAME=homeassistant-dev
  PATCH_FILE_LOCAL=docs/examples/ha_test_instance/heima_dev_options_patch.json

Example:
  scripts/patch_heima_dev_options.sh
  REMOTE_HOST=user@host scripts/patch_heima_dev_options.sh
EOF
}

DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|-n)
      DRY_RUN=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "$PATCH_FILE_LOCAL" ]]; then
  echo "Error: patch file not found: $PATCH_FILE_LOCAL" >&2
  exit 1
fi

REMOTE_PATCH_PATH="${REMOTE_BASE}/${PATCH_FILE_REMOTE_NAME}"

if [[ "$DRY_RUN" == "true" ]]; then
  echo "[dry-run] Would copy patch to ${REMOTE_HOST}:${REMOTE_PATCH_PATH}"
  echo "[dry-run] Would stop container: ${CONTAINER_NAME}"
  echo "[dry-run] Would backup and patch ${CONFIG_ENTRIES_PATH}"
  echo "[dry-run] Would start container: ${CONTAINER_NAME}"
  exit 0
fi

container_was_stopped=false
cleanup() {
  if [[ "$container_was_stopped" == "true" ]]; then
    echo "Ensuring HA-dev container is running (${CONTAINER_NAME})..."
    ssh "$REMOTE_HOST" "docker start '${CONTAINER_NAME}' >/dev/null 2>&1 || true" || true
  fi
}
trap cleanup EXIT

echo "Copying patch file to remote..."
scp "$PATCH_FILE_LOCAL" "${REMOTE_HOST}:${REMOTE_PATCH_PATH}"

echo "Stopping HA-dev container (${CONTAINER_NAME})..."
ssh "$REMOTE_HOST" "docker stop '${CONTAINER_NAME}'"
container_was_stopped=true

echo "Applying patch to Heima options..."
ssh "$REMOTE_HOST" "
  set -euo pipefail
  command -v jq >/dev/null 2>&1
  cd '${REMOTE_BASE}'
  test -f '${CONFIG_ENTRIES_PATH}'
  cp '${CONFIG_ENTRIES_PATH}' '${CONFIG_ENTRIES_PATH}.bak.'\$(date +%Y%m%d%H%M%S)
  jq --argfile patch '${PATCH_FILE_REMOTE_NAME}' \
    '(.data.entries) |= map(
      if .domain == \"heima\" then
        .options = (.options * \$patch)
      else
        .
      end
    )' \
    '${CONFIG_ENTRIES_PATH}' > '${CONFIG_ENTRIES_PATH}.tmp'
  mv '${CONFIG_ENTRIES_PATH}.tmp' '${CONFIG_ENTRIES_PATH}'
"

echo "Starting HA-dev container (${CONTAINER_NAME})..."
ssh "$REMOTE_HOST" "docker start '${CONTAINER_NAME}'"
container_was_stopped=false

echo "Patch applied successfully."
