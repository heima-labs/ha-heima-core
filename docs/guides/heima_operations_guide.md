# Heima — Operations Guide

Practical guidance for monitoring Heima over time.

This guide is for day-to-day operation, not for implementation details.

Canonical references:
- [heima_monitoring_spec.md](/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/docs/specs/core/heima_monitoring_spec.md)
- [heima_test_lab_dashboard.yaml](/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/docs/examples/ha_test_instance/docker/ha_config/dashboards/heima_test_lab_dashboard.yaml)

## What To Check

The operational questions are:

1. Is Heima healthy?
2. Is it learning anything useful?
3. Are configured capabilities actually active?
4. Is the system improving, stable, or degrading?

## Daily Routine

Use this when you want a fast operational check.

Main command:

```bash
source scripts/.env
python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
```

What a healthy result looks like:
- `verdict: healthy`
- `config_issue_total: 0`
- `Warnings: none`
- at least some configured reactions if you expect runtime value

Things that deserve attention:
- `verdict: attention_needed` or `degraded`
- non-zero `config_issue_total`
- stale pending proposals
- active security breach candidates
- configured reactions stuck blocked for long periods

## Weekly Review

Use this to understand whether learning is progressing or stalling.

Main commands:

```bash
source scripts/.env
python3 scripts/learning_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --review
```

What to look for:
- which families are active
- which enabled families are still quiet
- whether pending proposals are understandable
- whether learned capabilities are turning into configured reactions

Healthy pattern:
- some families active, but not noisy
- pending proposals are few and interpretable
- configured reactions exist for useful capabilities

Red flags:
- long periods with no meaningful evidence growth
- repeated low-confidence or stale proposals
- configured capabilities that never become operational

## Tracking Over Time

Use snapshots if you want to compare the system across days or weeks.

Create a snapshot:

```bash
source scripts/.env
python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --snapshot-out tmp/heima_ops_snapshot.json
```

Compare against a previous snapshot:

```bash
source scripts/.env
python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --compare-to tmp/heima_ops_snapshot.json
```

Compact review output:

```bash
source scripts/.env
python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --review --compare-to tmp/heima_ops_snapshot.json
```

Useful deltas:
- `pending_total_delta`
- `active_family_total_delta`
- `configured_reaction_total_delta`
- `camera_breach_candidate_total_delta`
- `security_presence_blocked_total_delta`

## Dashboard Usage

If you use the test house dashboard, these views map well to the operating workflow:

- `Heima Monitoring`
  - quick daily read
- `Heima Investigation`
  - use when something looks wrong or confusing
- `Heima Learning Review`
  - slower review of learning progress and runtime value

## Recommended Operator Flow

For a normal week:

1. Run `ops_audit.py` for a fast health check.
2. If the verdict is not healthy, inspect warnings first.
3. If behavior still looks odd, use the investigation dashboard or `diagnostics.py`.
4. Once or twice a week, run `learning_audit.py`.
5. Save periodic snapshots if you want to measure progress over time.

## When To Escalate Investigation

Use deeper diagnostics when:
- `config_issue_total` stops returning to zero
- a family you expect to learn stays quiet for too long
- proposal backlog keeps growing
- reactions are configured but never active
- security-related warnings appear repeatedly

Useful commands:

```bash
source scripts/.env
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section engine
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section learning
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section reactions
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section security_camera_evidence
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section security_presence
```

## Practical Rule

Prefer a small number of stable signals over many noisy ones.

A Heima instance that learns a few useful things clearly is healthier than one that produces many weak proposals and ambiguous runtime states.
