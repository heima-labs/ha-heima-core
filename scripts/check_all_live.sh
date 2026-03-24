#!/usr/bin/env bash
set -euo pipefail

# Load local env overrides if present (not committed)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

HA_URL="${HA_URL:-http://127.0.0.1:8123}"
HA_TOKEN="${HA_TOKEN:-}"
PERSON_SLUG="${PERSON_SLUG:-}"
SUITE_TIER="${SUITE_TIER:-live_e2e}"
SKIP_PREFIXES=()

SETUP_SCRIPTS=(
  "scripts/recover_test_lab_config.py"
  "scripts/live_tests/006_restore_learning_fixtures.sh"
)

LIVE_E2E_SCRIPTS=(
  "scripts/live_tests/000_live_smoke.py"
  "scripts/live_tests/010_config_flow.py"
  "scripts/live_tests/011_room_source_learning_signals.py"
  "scripts/live_tests/012_house_state_general_config.py"
  "scripts/live_tests/025_lighting_learning_live.py"
  "scripts/live_tests/026_room_signal_assist_live.py"
  "scripts/live_tests/027_room_cooling_assist_live.py"
  "scripts/live_tests/028_room_air_quality_assist_live.py"
  "scripts/live_tests/028b_room_darkness_lighting_assist_live.py"
  "scripts/live_tests/029_presence_live.py"
  "scripts/live_tests/040_security_mismatch_runtime.py"
  "scripts/live_tests/050_calendar_domain.py"
)

SEEDED_INTEGRATION_SCRIPTS=(
  "scripts/live_tests/015_learning_reset.sh"
  "scripts/live_tests/020_learning_pipeline.py"
  "scripts/live_tests/060_lighting_schedule.py"
)

DIAGNOSTIC_SCRIPTS=(
  "scripts/live_tests/030_learning_proposals_diag.py"
)

usage() {
  cat <<'EOF'
Usage:
  HA_TOKEN=<token> [PERSON_SLUG=<slug>] ./scripts/check_all_live.sh [--ha-url URL] [--tier live_e2e] [--skip 015]

Execution model:
- runs an explicit ordered manifest for the selected tier
- avoids mixing setup / seeded / diagnostic scripts into the canonical live E2E lane
- when `--tier live_e2e` is selected, setup prerequisites run first so the lab
  starts from the expected baseline

Options:
  --tier <name>       one of: setup, live_e2e, seeded_integration, diagnostic, all
  --skip <prefixes>   comma-separated numeric prefixes to skip (e.g. --skip 005,015)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ha-url)
      HA_URL="${2:-}"; shift 2;;
    --tier)
      SUITE_TIER="${2:-}"; shift 2;;
    --skip)
      IFS=',' read -ra SKIP_PREFIXES <<< "${2:-}"; shift 2;;
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
case "$SUITE_TIER" in
  setup)
    files=("${SETUP_SCRIPTS[@]}")
    ;;
  live_e2e)
    files=(
      "${SETUP_SCRIPTS[@]}"
      "${LIVE_E2E_SCRIPTS[@]}"
    )
    ;;
  seeded_integration)
    files=("${SEEDED_INTEGRATION_SCRIPTS[@]}")
    ;;
  diagnostic)
    files=("${DIAGNOSTIC_SCRIPTS[@]}")
    ;;
  all)
    files=(
      "${SETUP_SCRIPTS[@]}"
      "${LIVE_E2E_SCRIPTS[@]}"
      "${SEEDED_INTEGRATION_SCRIPTS[@]}"
      "${DIAGNOSTIC_SCRIPTS[@]}"
    )
    ;;
  *)
    echo "Unknown tier: $SUITE_TIER" >&2
    usage
    exit 2
    ;;
esac

for file in "${files[@]}"; do
  if [[ ! -x "$file" ]]; then
    echo "Script not executable or not found: $file" >&2
    exit 2
  fi
  base="$(basename "$file")"
  should_skip=false
  for prefix in "${SKIP_PREFIXES[@]}"; do
    if [[ "$base" == "${prefix}"* ]]; then should_skip=true; break; fi
  done
  if $should_skip; then
    echo "== Skipping ${base} (--skip) =="
    continue
  fi
  echo "== Running ${base} =="
  case "$base" in
    *.py)
      args=(--ha-url "$HA_URL" --ha-token "$HA_TOKEN")
      if [[ "$base" == 020_* ]]; then
        if [[ -z "$PERSON_SLUG" ]]; then
          echo "PERSON_SLUG is required for $base" >&2
          exit 2
        fi
        args+=(--person-slug "$PERSON_SLUG")
      fi
      "$file" "${args[@]}"
      ;;
    *.sh)
      HA_URL="$HA_URL" HA_TOKEN="$HA_TOKEN" PERSON_SLUG="$PERSON_SLUG" "$file"
      ;;
    *)
      echo "Skipping unsupported file: $base"
      ;;
  esac
done

echo "Suite '$SUITE_TIER' passed."
