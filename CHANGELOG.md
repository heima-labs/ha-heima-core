# Changelog

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
