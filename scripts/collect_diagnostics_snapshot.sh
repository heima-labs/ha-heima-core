#!/usr/bin/env bash
# Collect a timestamped diagnostics snapshot for offline pattern analysis
# (entity/action/weekday recurrence, anomaly findings, proposal backlog).
# Meant to be run periodically (e.g. via cron every few hours) so snapshots
# from different times of day can be compared.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# HA_URL and HA_TOKEN must already be set in the shell (export, or `source` an
# env file yourself) before running this script. It does not load any env file
# on its own.
HA_URL="${HA_URL:-http://127.0.0.1:8123}"
HA_TOKEN="${HA_TOKEN:-}"

if [[ -z "$HA_TOKEN" ]]; then
  echo "ERROR: HA_TOKEN is required. Export it or source an env file before running this script," >&2
  echo "e.g.: source scripts/.env-prod && $0" >&2
  exit 2
fi

TS="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="$REPO_ROOT/debug/diagnostics_snapshots/$TS"
mkdir -p "$OUT_DIR"

cd "$REPO_ROOT"

run_step() {
  local label="$1"
  local out_file="$2"
  shift 2
  echo "== $label =="
  if "$@" > "$out_file" 2>&1; then
    echo "   ok -> $out_file"
  else
    echo "   FAILED (exit $?) -> $out_file (see file for details)"
  fi
}

# Full runtime diagnostics: event_store, proposals, learning, lighting, reactions,
# house_state, engine, etc. — the richest source for entity/action/weekday patterns.
run_step "diagnostics.py --section all" "$OUT_DIR/diagnostics_all.txt" \
  python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section all

# Readable learning summary: pending/accepted/rejected/stale breakdown, templates,
# lighting collisions.
run_step "learning_audit.py" "$OUT_DIR/learning_audit.txt" \
  python3 scripts/learning_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"

# Compact operational summary + a stable JSON snapshot for longitudinal comparison
# (--compare-to can later diff two of these snapshot files against each other).
run_step "ops_audit.py --review --snapshot-out" "$OUT_DIR/ops_review.txt" \
  python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" \
    --review --snapshot-out "$OUT_DIR/ops_snapshot.json"

# Proposal backlog grouping/duplication audit, so already-seen/rejected proposals
# aren't re-suggested.
run_step "proposal_backlog_audit.py" "$OUT_DIR/proposal_backlog.txt" \
  python3 scripts/proposal_backlog_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"

echo
echo "Snapshot collected in: $OUT_DIR"
