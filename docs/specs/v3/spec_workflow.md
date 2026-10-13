# V3 specification change protocol

This protocol is for the **planned V3 design**, not the implemented V2 runtime. Its compact
machine-readable navigation map is [`contract_registry.json`](contract_registry.json).
The registry records ownership and evidence; it does not restate normative behavior. The
Layer 0–6 and Layer 8 specs remain authoritative. The overview and recap explain them. The backlog
preserves chronological decisions and findings. Historical drafts cannot override a layer spec.

## Work one bounded issue at a time

1. Locate the issue and its approved decisions in `docs/v3_backlog.md`. Read the registry
   entries for its owning contracts, their dependencies and the relevant acceptance sections.
   Read other sections only when an explicit dependency leads there.
2. Write a short impact record before editing: existing decision, exact unresolved gap,
   reusable construct, affected sections, V2-to-V3 constraints, and counterexamples across
   distinct sensor/actuator kinds. Keep an unresolved product choice visible until the
   developer decides it. Reopen an approved decision only with a specific contradiction.
3. Modify the authoritative owner and its affected acceptance criteria. Reconcile dependent
   specs, overview, recap, examples and backlog status in the same change. Add registry
   references for the bounded contract slice. Do not clone normative rules into the registry.
4. Review a scenario matrix against the owning text and dependency closure. Include normal,
   unavailable, recovery, cancellation, concurrency and safety cases when applicable.
   Run `python3 scripts/check_v3_specs.py`. The script checks structure and references;
   a semantic review must check the actual behavior.

Run `python3 scripts/check_v3_specs.py --open` to derive the current CA4 queue from
each issue's status. For a mapped issue, `--issue CA4-18` prints its contract closure.

## Evidence and status

`DONE (specification readiness)` means the normative rule, dependent references and
acceptance scenarios have been reviewed. It does not mean V3 code exists or runtime tests
passed. Every review record must say which evidence exists and which has not been run.
If a review finds an unresolved contradiction, keep the issue open and record the exact case.
`git diff --check` checks patch hygiene only. The first reviewed slice, CA4-18, demonstrates
the format in [`reviews/CA4-18.md`](reviews/CA4-18.md).

The registry is intentionally incremental: it inventories all current authoritative layer
files and records contract-level dependencies for reviewed slices. Add the next issue's
contract-level entries when it is analyzed. Do not label unmapped contracts as reviewed.
