#!/usr/bin/env bash
set -euo pipefail

# Deploy Heima custom component to remote HA instances.
#
# Targets:
# - prod -> $REMOTE_HOST:$REMOTE_PROD_BASE
# - dev  -> $REMOTE_HOST:$REMOTE_DEV_BASE
#
# By default this script syncs:
#   ./custom_components/heima
# into:
#   <target>/custom_components/heima

REMOTE_HOST="${REMOTE_HOST:-user@ha-host}"
REMOTE_PROD_BASE="HA"
REMOTE_DEV_BASE="HA/HA-dev/config"
SOURCE_DIR="custom_components/heima/"
DEV_CONTAINER_NAME="${DEV_CONTAINER_NAME:-homeassistant-dev}"

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy_heima.sh --target prod|dev|both [--mode rsync|tar] [--dry-run]

Examples:
  scripts/deploy_heima.sh --target dev
  scripts/deploy_heima.sh --target prod
  scripts/deploy_heima.sh --target both
  scripts/deploy_heima.sh --target dev --mode tar
  scripts/deploy_heima.sh --target both --dry-run

Environment overrides:
  DEV_CONTAINER_NAME=homeassistant-dev
EOF
}

TARGET=""
DRY_RUN=false
MODE="rsync"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target|-t)
      TARGET="${2:-}"
      shift 2
      ;;
    --dry-run|-n)
      DRY_RUN=true
      shift
      ;;
    --mode|-m)
      MODE="${2:-}"
      shift 2
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

if [[ -z "$TARGET" ]]; then
  echo "Error: --target is required." >&2
  usage
  exit 1
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Error: source directory not found: $SOURCE_DIR" >&2
  exit 1
fi

rsync_base_args=(
  -av
  --delete
)

if [[ "$DRY_RUN" == "true" ]]; then
  rsync_base_args+=(--dry-run)
fi

deploy_to_rsync() {
  local remote_base="$1"
  local remote_path="${REMOTE_HOST}:${remote_base}/custom_components/heima/"

  echo "Deploying with rsync to ${remote_path}"
  rsync "${rsync_base_args[@]}" "$SOURCE_DIR" "$remote_path"
}

deploy_to_tar() {
  local remote_base="$1"
  local remote_dir="${remote_base}/custom_components/heima"
  local -a tar_args
  tar_args=(-C "$SOURCE_DIR" -cf - .)

  # macOS/BSD tar metadata can generate noisy warnings on Linux extraction.
  # Prefer explicit flags when available; always disable copyfile metadata.
  if tar --help 2>/dev/null | grep -q -- '--no-xattrs'; then
    tar_args=(--no-xattrs "${tar_args[@]}")
  fi
  if tar --help 2>/dev/null | grep -q -- '--no-mac-metadata'; then
    tar_args=(--no-mac-metadata "${tar_args[@]}")
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[dry-run] Would deploy with tar to ${REMOTE_HOST}:${remote_dir}/"
    return 0
  fi

  echo "Deploying with tar stream to ${REMOTE_HOST}:${remote_dir}/"
  ssh "$REMOTE_HOST" "mkdir -p '${remote_base}/custom_components' && rm -rf '${remote_dir}' && mkdir -p '${remote_dir}'"
  COPYFILE_DISABLE=1 tar "${tar_args[@]}" | ssh "$REMOTE_HOST" "tar -C '${remote_dir}' -xf -"
}

deploy_to() {
  local remote_base="$1"
  case "$MODE" in
    rsync)
      deploy_to_rsync "$remote_base"
      ;;
    tar)
      deploy_to_tar "$remote_base"
      ;;
    *)
      echo "Invalid --mode value: $MODE (expected: rsync|tar)" >&2
      exit 1
      ;;
  esac
}

restart_dev_instance() {
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[dry-run] Would restart dev container: ${DEV_CONTAINER_NAME}"
    return 0
  fi
  echo "Restarting dev instance container (${DEV_CONTAINER_NAME})..."
  ssh "$REMOTE_HOST" "docker restart '${DEV_CONTAINER_NAME}' >/dev/null"
  echo "Dev instance restarted."
}

case "$TARGET" in
  prod)
    deploy_to "$REMOTE_PROD_BASE"
    ;;
  dev)
    deploy_to "$REMOTE_DEV_BASE"
    restart_dev_instance
    ;;
  both)
    deploy_to "$REMOTE_PROD_BASE"
    deploy_to "$REMOTE_DEV_BASE"
    restart_dev_instance
    ;;
  *)
    echo "Invalid --target value: $TARGET (expected: prod|dev|both)" >&2
    exit 1
    ;;
esac

echo "Deploy completed."
