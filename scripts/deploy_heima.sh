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
#
# For prod deployments only, it can also sync selected developer/operator scripts
# into:
#   <prod>/scripts

# Load local env overrides if present (not committed)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

REMOTE_HOST="${REMOTE_HOST:-user@ha-host}"
REMOTE_PROD_BASE="${REMOTE_PROD_BASE:-HA}"
REMOTE_DEV_BASE="${REMOTE_DEV_BASE:-HA/HA-dev/config}"
SOURCE_DIR="custom_components/heima/"
DEV_CONTAINER_NAME="${DEV_CONTAINER_NAME:-homeassistant-dev}"
if [[ -z "${PROD_DEPLOY_SCRIPTS+x}" ]]; then
  PROD_DEPLOY_SCRIPTS="scripts/generate_debug_dashboard.py"
fi
if [[ -z "${SCRIPT_DEPLOY_SHARED_LIBS+x}" ]]; then
  SCRIPT_DEPLOY_SHARED_LIBS="scripts/lib/ha_client.py"
fi

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
  PROD_DEPLOY_SCRIPTS="scripts/generate_debug_dashboard.py"
  SCRIPT_DEPLOY_SHARED_LIBS="scripts/lib/ha_client.py"

Set PROD_DEPLOY_SCRIPTS="" to disable prod script deployment.
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
  --exclude='__pycache__/'
  --exclude='*.pyc'
  --exclude='*.pyo'
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
  tar_args=(
    --exclude='./__pycache__'
    --exclude='./*/__pycache__'
    --exclude='*.pyc'
    --exclude='*.pyo'
    -C "$SOURCE_DIR"
    -cf -
    .
  )

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

_append_unique_path() {
  local candidate="$1"
  local existing
  for existing in "${deploy_script_paths[@]}"; do
    if [[ "$existing" == "$candidate" ]]; then
      return 0
    fi
  done
  deploy_script_paths+=("$candidate")
}

_build_deploy_script_paths() {
  deploy_script_paths=()

  local script_path
  # shellcheck disable=SC2206
  local configured_scripts=($PROD_DEPLOY_SCRIPTS)
  for script_path in "${configured_scripts[@]}"; do
    [[ -z "$script_path" ]] && continue
    if [[ "$script_path" = /* || "$script_path" == *".."* ]]; then
      echo "Error: script deploy path must be a relative repo path without '..': $script_path" >&2
      exit 1
    fi
    if [[ ! -f "$script_path" ]]; then
      echo "Error: script deploy path not found: $script_path" >&2
      exit 1
    fi
    _append_unique_path "$script_path"
  done

  if [[ "${#deploy_script_paths[@]}" -gt 0 && -n "$SCRIPT_DEPLOY_SHARED_LIBS" ]]; then
    # shellcheck disable=SC2206
    local shared_libs=($SCRIPT_DEPLOY_SHARED_LIBS)
    for script_path in "${shared_libs[@]}"; do
      [[ -z "$script_path" ]] && continue
      if [[ "$script_path" = /* || "$script_path" == *".."* ]]; then
        echo "Error: shared script deploy path must be a relative repo path without '..': $script_path" >&2
        exit 1
      fi
      if [[ ! -f "$script_path" ]]; then
        echo "Error: shared script deploy path not found: $script_path" >&2
        exit 1
      fi
      _append_unique_path "$script_path"
    done
  fi
}

deploy_prod_scripts_rsync() {
  local remote_base="$1"
  local remote_path="${REMOTE_HOST}:${remote_base}/"

  _build_deploy_script_paths
  if [[ "${#deploy_script_paths[@]}" -eq 0 ]]; then
    echo "No prod scripts configured for deployment."
    return 0
  fi

  echo "Deploying prod scripts with rsync to ${remote_path}"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[dry-run] Would ensure remote scripts directory exists: ${REMOTE_HOST}:${remote_base}/scripts"
  else
    ssh "$REMOTE_HOST" "mkdir -p '${remote_base}/scripts/lib'"
  fi
  rsync "${rsync_base_args[@]}" --relative "${deploy_script_paths[@]}" "$remote_path"
}

deploy_prod_scripts_tar() {
  local remote_base="$1"

  _build_deploy_script_paths
  if [[ "${#deploy_script_paths[@]}" -eq 0 ]]; then
    echo "No prod scripts configured for deployment."
    return 0
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[dry-run] Would deploy prod scripts with tar to ${REMOTE_HOST}:${remote_base}/"
    printf '[dry-run] Scripts:'
    printf ' %s' "${deploy_script_paths[@]}"
    printf '\n'
    return 0
  fi

  echo "Deploying prod scripts with tar stream to ${REMOTE_HOST}:${remote_base}/"
  ssh "$REMOTE_HOST" "mkdir -p '${remote_base}/scripts/lib'"
  COPYFILE_DISABLE=1 tar -cf - "${deploy_script_paths[@]}" | ssh "$REMOTE_HOST" "tar -C '${remote_base}' -xf -"
}

deploy_prod_scripts() {
  local remote_base="$1"
  case "$MODE" in
    rsync)
      deploy_prod_scripts_rsync "$remote_base"
      ;;
    tar)
      deploy_prod_scripts_tar "$remote_base"
      ;;
    *)
      echo "Invalid --mode value: $MODE (expected: rsync|tar)" >&2
      exit 1
      ;;
  esac
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
    deploy_prod_scripts "$REMOTE_PROD_BASE"
    ;;
  dev)
    deploy_to "$REMOTE_DEV_BASE"
    restart_dev_instance
    ;;
  both)
    deploy_to "$REMOTE_PROD_BASE"
    deploy_prod_scripts "$REMOTE_PROD_BASE"
    deploy_to "$REMOTE_DEV_BASE"
    restart_dev_instance
    ;;
  *)
    echo "Invalid --target value: $TARGET (expected: prod|dev|both)" >&2
    exit 1
    ;;
esac

echo "Deploy completed."
