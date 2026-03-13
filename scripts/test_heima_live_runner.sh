#!/usr/bin/env bash
set -euo pipefail

# End-to-end live runner:
# 1) deploy Heima code
# 2) optionally patch HA-dev Heima options
# 3) run Python live smoke tests

# Load local env overrides if present (not committed)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

DEPLOY_TARGET="dev"
DEPLOY_MODE="tar"
SKIP_DEPLOY=false
SKIP_PATCH=false
HA_URL="${HA_URL:-http://homeassistant.local:8123}"
HA_TOKEN="${HA_TOKEN:-}"
TIMEOUT_S="${TIMEOUT_S:-45}"
POLL_S="${POLL_S:-1}"

usage() {
  cat <<'EOF'
Usage:
  HA_TOKEN=<token> scripts/test_heima_live_runner.sh [options]

Options:
  --target dev|prod|both   Deploy target (default: dev)
  --mode rsync|tar         Deploy mode (default: tar)
  --skip-deploy            Skip deploy step
  --skip-patch             Skip dev options patch step
  --ha-url URL             HA URL for live tests (default: http://homeassistant.local:8123)
  --timeout-s N            Wait timeout for state checks (default: 45)
  --poll-s N               Poll interval (default: 1)
  -h, --help               Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      DEPLOY_TARGET="${2:-}"
      shift 2
      ;;
    --mode)
      DEPLOY_MODE="${2:-}"
      shift 2
      ;;
    --skip-deploy)
      SKIP_DEPLOY=true
      shift
      ;;
    --skip-patch)
      SKIP_PATCH=true
      shift
      ;;
    --ha-url)
      HA_URL="${2:-}"
      shift 2
      ;;
    --timeout-s)
      TIMEOUT_S="${2:-}"
      shift 2
      ;;
    --poll-s)
      POLL_S="${2:-}"
      shift 2
      ;;
    -h|--help)
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

if [[ -z "$HA_TOKEN" ]]; then
  echo "Error: HA_TOKEN is required." >&2
  exit 1
fi

if [[ "$SKIP_DEPLOY" == "false" ]]; then
  echo "== Step 1/3: deploy =="
  scripts/deploy_heima.sh --target "$DEPLOY_TARGET" --mode "$DEPLOY_MODE"
else
  echo "== Step 1/3: deploy (skipped) =="
fi

if [[ "$SKIP_PATCH" == "false" ]]; then
  if [[ "$DEPLOY_TARGET" == "prod" ]]; then
    echo "== Step 2/3: patch (skipped for prod target) =="
  else
    echo "== Step 2/3: patch dev Heima options =="
    scripts/patch_heima_dev_options.sh
  fi
else
  echo "== Step 2/3: patch (skipped) =="
fi

echo "== Step 3/3: run live smoke tests =="
scripts/live_tests/000_live_smoke.py \
  --ha-url "$HA_URL" \
  --ha-token "$HA_TOKEN" \
  --timeout-s "$TIMEOUT_S" \
  --poll-s "$POLL_S"

echo "Runner completed."
