# V3 specification work in this worktree

The V3 layer specifications under `docs/specs/v3/` are authoritative for planned V3 behavior.
They do not describe the implemented V2 runtime on `main`. Read
`docs/specs/v3/contract_registry.json` and `docs/specs/v3/spec_workflow.md` first. Use the
registry to read only the owning contract and its dependency closure for the current issue.
The backlog is the decision and issue history. The architecture map
(`docs/specs/v3/architecture_overview_defined_layers.md`) is the one orientation document, not a
competing normative contract; read it whole for the big picture. Root-level V3 drafts, the old
Graphviz diagram and `docs/v3_architecture_recap.md` are historical.

Before editing a V3 contract, make a short impact record: the already approved decision,
the exact gap, existing constructs to reuse, owning and dependent sections, V2-to-V3 design
constraints, and counterexamples across actuator or sensor kinds. Present unresolved product
choices to the developer before making them definitive. Do not reopen an approved choice
without a concrete contradiction or missing case. Never mark an item specification-ready
from `git diff --check` alone. Record semantic scenario evidence and separately state whether
any executable/runtime test ran. Update affected acceptance criteria, registry references and the
architecture map in the same slice; raise its "Reconciled through" line when the issue closes. Run `python3 scripts/check_v3_specs.py`.
Use `python3 scripts/check_v3_specs.py --open` for the current CA4 queue; the dated
correction sequence at the end of the backlog is historical.

Do not change V2 code or its active specifications as part of a V3 documentation correction.
