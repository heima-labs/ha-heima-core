# Heima Monitoring Spec

Status: Draft  
Scope: Product operability, ongoing validation, learning progress review  
Target: v1.x operational surfaces

## Purpose

Heima needs a bounded but serious monitoring surface so an operator can answer, over time:

1. Is Heima healthy and functioning?
2. Is Heima learning meaningful patterns?
3. Are learned and configured capabilities actually active?
4. Is the system improving, stagnating, or degrading?

This spec defines the minimum monitoring model for v1.x.

It does **not** define:

- a custom frontend panel implementation
- long-term timeseries storage architecture
- telemetry export to external SaaS systems

## Monitoring Layers

Monitoring should be split into three layers.

### 1. Daily Operations

Fast operational view for day-to-day use.

Questions:

- Is the runtime healthy?
- Is the current house/security state sensible?
- Are key reactions active, muted, or blocked?
- Is there proposal backlog that needs review?

Expected surfaces:

- production dashboard
- compact diagnostics summary

### 2. Weekly Learning Review

Slower review of how the system is evolving.

Questions:

- Which families are learning?
- Which families are not producing enough evidence?
- Which proposals are pending, stale, or repeatedly blocked?
- Are follow-up/tuning proposals emerging where expected?

Expected surfaces:

- audit script
- learning-focused dashboard/debug surface

### 3. Debug / Investigation

Deep inspection for anomalies, regressions, or confusing behavior.

Questions:

- Why did Heima decide X?
- Why did Heima not decide Y?
- Which source, guard, or derived plan blocked the expected behavior?

Expected surfaces:

- full diagnostics payload
- debug dashboard
- feature-specific sections in diagnostics tooling

## Core Monitoring Areas

The monitoring model should always be grouped into these areas:

1. `Health`
2. `House State`
3. `Learning`
4. `Proposals`
5. `Reactions`
6. `Security`
7. `Feature-specific families`

Feature-specific families currently important enough to deserve explicit monitoring include:

- `security_presence_simulation`
- `security_camera_evidence`
- `heating`

## Daily Operations Contract

The daily operations surface should expose at least:

### Health

- engine health status
- last evaluation reason
- config invalid / config issue count
- last event summary
- event store summary

### House State

- current `house_state`
- `house_state_reason`
- `anyone_home`
- `people_count`
- active/pending state candidates when relevant

### Security

- current `security_state`
- `security_reason`
- active camera evidence count
- breach candidate count

### Reactions

- configured reaction count
- muted reaction count
- blocked reaction count
- active tonight count for dynamic families where relevant

### Proposals

- pending proposal count
- families with pending proposals
- latest/highest-confidence proposal examples

## Weekly Learning Review Contract

The weekly learning review should expose at least:

### Learning by Family

For each enabled family:

- enabled / disabled
- proposals generated recently
- accepted vs pending
- evidence sufficiency status
- representative `weeks_observed`
- representative confidence band

### Learning Trend Signals

- families with no meaningful evidence growth
- families producing repeated low-confidence proposals
- families producing useful tuning/follow-up proposals
- stale pending proposal count

### Outcome Summary

- accepted proposal families
- configured learned-origin reactions
- families that are active in runtime vs families that remain diagnostic-only

## Debug / Investigation Contract

The debug surface should make it easy to inspect:

- per-domain diagnostics
- proposal explainability
- configured reaction diagnostics
- scheduler jobs
- blocked reasons
- feature-specific traces

The debug surface should prefer:

- compact summaries first
- raw nested diagnostics second

## Metrics

The monitoring system should surface metrics in three classes.

### A. Health Metrics

- `engine_health_ok`
- `config_issue_total`
- `event_emit_total`
- `event_drop_total`
- `scheduler_job_total`
- `scheduler_overdue_total` if available later

### B. Learning Metrics

- `learning_family_enabled_total`
- `learning_family_active_total`
- `pending_proposal_total`
- `pending_proposal_total_by_family`
- `accepted_proposal_total_by_family`
- `stale_proposal_total`
- `insufficient_evidence_total_by_family`

### C. Runtime Value Metrics

- `configured_reaction_total`
- `muted_reaction_total`
- `blocked_reaction_total`
- `dynamic_ready_total`
- `dynamic_waiting_total`
- `dynamic_insufficient_evidence_total`
- `breach_candidate_total`
- `camera_active_evidence_total`

## Good vs Bad Signals

The monitoring surface should help distinguish healthy progress from problematic drift.

### Healthy Signals

- house-state transitions remain explainable and stable
- key families produce some proposals but not noisy proposal floods
- accepted learned capabilities become active in runtime
- dynamic families show `ready_tonight` or equivalent healthy operational states
- insufficient evidence remains temporary, not permanent

### Red Flags

- families expected to learn produce no proposals for long periods
- many proposals remain low-confidence or stale
- configured reactions stay blocked for long periods
- frequent `config_invalid` or unavailable-source diagnostics
- runtime surfaces show many capabilities that are configured but never active

## Recommended Surfaces

### Production Dashboard

Purpose:

- quick daily reading
- low-noise operational view

Should contain:

- Health
- House State
- Security
- Reactions
- Proposal backlog summary

### Debug Dashboard

Purpose:

- investigation and feature verification

Should contain:

- diagnostics-oriented summaries
- active traces
- family-specific runtime sections
- scheduler and reaction details

### Audit Script

Purpose:

- compact textual review during maintenance

Suggested command family:

- `scripts/learning_audit.py`
- future `scripts/ops_audit.py`

The audit output should be readable without requiring the full diagnostics payload.

## Backlog

### Ops-A1 Daily Production Surface

Deliver:

- compact dashboard section(s) for health, state, reactions, proposal backlog

Acceptance:

- an operator can assess runtime health in under one minute

### Ops-A2 Debug Surface

Deliver:

- richer debug dashboard sections for diagnostics-oriented inspection

Acceptance:

- feature debugging does not require opening raw JSON first

### Ops-A3 Learning Review Surface

Deliver:

- family summaries and trend-oriented review surface

Acceptance:

- an operator can tell which families are learning, stalled, or noisy

### Ops-A4 Audit Script

Deliver:

- CLI summary for periodic checks

Acceptance:

- a single command summarizes health, learning, proposals, and runtime value

### Ops-A5 Longitudinal Monitoring

Deliver:

- stable snapshot/export shape for historical review

Acceptance:

- repeated audits can be compared over time without reading full diagnostics dumps

## First Implementation Slice

The first monitoring slice should be:

1. `Ops-A1`
2. part of `Ops-A3`
3. a minimal `Ops-A4`

Concretely:

- compact production dashboard additions
- family summaries for learning/proposals/reactions
- one textual audit command focused on current health and learning status

## Implementation Notes

v1.x should prefer reusing existing sources of truth:

- `engine.diagnostics()`
- `scripts/diagnostics.py`
- `scripts/learning_audit.py`
- dashboard example YAML files

The first monitoring implementation should avoid:

- inventing a separate parallel status model
- duplicating diagnostics logic into dashboards
- creating a custom frontend before the summary contract is stable
