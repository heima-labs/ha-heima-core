# Changelog

## [0.13.0] — 2026-08-21

- Recovery no longer blocks stabilization on motion/occupancy/presence entities that are
  `unavailable` only because they haven't fired since restart. These entities stay visible in
  checkpoint differences and observability but no longer count toward the recovery unavailable
  ratio (`critical_entities` in admin observability now also reports `gating_total` /
  `gating_unavailable` alongside the full counts).

## [0.12.0] — 2026-08-20

- Runtime checkpoint and power recovery: post-review hardening — missing critical entities are
  classified as unavailable instead of being silently omitted from recovery ratios; checkpoint
  writes are guarded against concurrent recovery; recovery diagnostics expose wall-clock
  timestamps for every phase transition; `ApplyStep.recovery_policy` gained an explicit allow
  vocabulary so camera privacy enforcement can run during recovery when the alarm input is stable.
- Structured runtime source (`ApplyStepSource`): apply steps now carry a typed source (reaction,
  domain, admin command, resident response, timeout, recovery, system, test) instead of a
  free-form string. Legacy string sources remain accepted but are never authoritative. Recovery
  admin bypass, Manual Hold ownership, runtime confirmation provenance, script apply batches, and
  observability all derive from structured sources instead of parsing strings; raw actor ids are
  redacted everywhere they could otherwise leak (diagnostics, observability, checkpoints, logs,
  persisted stores).
- Reaction evaluation is now suppressed during active runtime recovery (except the camera privacy
  policy template, which must keep protecting the home), so scheduled reactions don't misfire or
  lose their trigger window while the system is still settling after a restart.
- `camera_evidence_sources` now accepts both list and dict-keyed-by-id shapes at every runtime
  call site, matching the Options Flow editor's existing tolerance; malformed entries are still
  surfaced as an installer diagnostic instead of being silently dropped.

## [0.11.0] — 2026-08-19

- Fix Hassfest `config_flow.py` file requirement by moving the config flow step
  implementation to `config_flow_steps/` and adding a `config_flow.py` entry point that
  re-exports `HeimaConfigFlow`/`HeimaOptionsFlowHandler`.
- Sort `manifest.json` keys per Hassfest convention (`domain`, `name`, then alphabetical).
- Remove the unsupported `domains` key from `hacs.json`.
- Add brand assets (`icon.png`, `icon@2x.png`) for HACS brand validation.

## [0.10.0] — 2026-07-07

- Release implicit camera privacy manual holds when the configured alarm transitions from
  `disarmed` to any armed state, allowing privacy policies to resume on the next arm cycle.
- Preserve explicit `manual_hold_entity` behavior: helper-backed holds still remain active until
  their helper is turned off.

## [0.9.0] — 2026-07-03

Merge v2 architecture into `main`. Replaces the v1 hardcoded DAG
(`InputNormalizer → People → Occupancy → Calendar → HouseState → Lighting → Heating → Security → Apply`)
with the declarative plugin DAG described in `docs/specs/heima_v2_spec.md`. 1594 tests passing.

Highlights (Phases A–AG, see `docs/v2_dev_plan.md` for full detail):

- Declarative domain DAG with `depends_on` ordering; core domains People → Occupancy → Activity →
  HouseState fixed, plugin domains (Lighting, Heating, Security, Calendar) sorted by dependency.
- `ActivityDomain` as the fourth core domain, with primitive activity detection and hysteresis.
- `InferenceEngine` v2, `OutcomeTracker` act→verify feedback loop, and per-cycle
  `IInvariantCheck` structural checks.
- Behavior analyzers for patterns, anomalies, lifecycle suggestions, and composite/cross-domain
  signals, routed through an approval-gated `ProposalEngine`.
- Proposal lifecycle management: grouping, temporal review bundles, replacement, retirement, and
  maintenance suggestions.
- `ManualHoldManager`: shared framework for respecting user intervention across domains.
- Camera privacy policies driven by alarm state and house-state conditions, authored through a
  domain-specific Policy Editor (Options Flow), built on the generic Policy Editor Framework.
- Installer alert channel, health entity, auto-discovery config flow, and installation validation.
- Room context model, tiered house-state feature enrichment, and global drift detection.
- Developer scripts, operational docs, and canonical specs translated to English (Phase AG); the
  runtime's intentional IT/EN localization for dynamic proposal/reaction text is unaffected.

Not yet merged: Phase AB (Smart Lighting Automation, unified) remains `PLANNED` and continues on a
dedicated branch after this merge.

## [0.8.0] — 2026-04-30

Baseline v1 — 660 test passanti. Punto di partenza per lo sviluppo v2.
