#!/usr/bin/env bash
set -euo pipefail

# Load local env overrides if present (not committed)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

HA_URL="${HA_URL:-http://127.0.0.1:8123}"
HA_TOKEN="${HA_TOKEN:-}"
LIVE_DIR="${LIVE_DIR:-scripts/live_tests}"
PERSON_SLUG="${PERSON_SLUG:-}"

usage() {
  cat <<'EOF'
Usage:
  HA_TOKEN=<token> [PERSON_SLUG=<slug>] ./scripts/check_all_live.sh [--ha-url URL] [--live-dir DIR]

Execution model:
- discovers all executable files in LIVE_DIR
- sorts by filename (alphabetical)
- executes each one in order

Naming convention:
- use numeric prefixes (e.g. 000_, 010_, 020_) to control ordering.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ha-url)
      HA_URL="${2:-}"; shift 2;;
    --live-dir)
      LIVE_DIR="${2:-}"; shift 2;;
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
if [[ ! -d "$LIVE_DIR" ]]; then
  echo "Live tests directory not found: $LIVE_DIR" >&2
  exit 2
fi

mapfile -t files < <(find "$LIVE_DIR" -maxdepth 1 -type f -perm -111 -print | sort)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "No executable test files found in $LIVE_DIR" >&2
  exit 2
fi

for file in "${files[@]}"; do
  base="$(basename "$file")"
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

echo "All live tests passed."

