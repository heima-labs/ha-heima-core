# Options Import/Export Spec

**Status:** Draft — pending developer approval, not implemented
**Created:** 2026-07-17
**Scope:** YAML-based export/import of the Heima config entry `options` payload
**Related:** `options_flow_spec.md` (normative schema), `options_flow_ux_spec.md`,
`policy_editor_framework_spec.md`, `heima_monitoring_spec.md`

---

## Motivation

Today the only way to read or write Heima's configuration is the step-by-step Options Flow UI.
That's the right primary surface for a resident-facing product, but it creates friction for the
**installer** role specifically (see `README.md` "Who is Heima for?"):

- Bulk edits (e.g. re-tuning several rooms at once) require walking the UI step by step, with no
  faster path.
- There is no diffable, versionable representation of a house's configuration — installers
  managing multiple houses have no way to compare, back up, or template configs across
  installations.

**Prior art, explicitly insufficient:** `scripts/patch_heima_dev_options.sh` already does a blunt
version of "edit options in bulk" — it SSHes into a dev host and applies a raw JSON merge patch
directly to the config entry inside HA's `.storage`, bypassing HA entirely. It is a dev-lab-only
tool: no validation, no schema awareness, unsafe against a production instance. This spec
formalizes a safe, validated equivalent that installers can use against a real running instance.

## Non-goals (overlap check against existing specs)

This is deliberately **not** a new configuration surface or a new source of truth:

- **`options_flow_spec.md` remains the single normative schema.** The persisted `config_entry.options`
  dict remains the only thing the runtime reads. No YAML file is ever read at startup or at
  runtime. Export/import is a point-in-time snapshot operation, not a live parallel config path —
  this avoids the two-sources-of-truth problem (config entry vs. a file on disk silently drifting
  apart).
- **This does not replace the Options Flow UI**, nor does it reopen the door to raw YAML as a
  domain-policy authoring surface. `policy_editor_framework_spec.md` explicitly rejected raw YAML
  for domain-specific policies as "too structured and domain-specific" — that reasoning still
  holds. Export/import operates on the same structured schema the Options Flow already validates;
  it is a bulk transport format for that schema, not a new schema or a new editing paradigm.
- **Unrelated to `CONFIG_SCHEMA`/`configuration.yaml` integration setup.** The hassfest
  `CONFIG_SCHEMA` warning fix (`cv.config_entry_only_config_schema`, see `__init__.py`) is about
  whether Heima can be *set up* from `configuration.yaml`. It stays as config-entry-only regardless
  of this feature. Import/export operates on an *existing* config entry's options, never on
  integration setup.

## Export

- Produces a YAML document that is a faithful, human-readable representation of the current
  `config_entry.options` dict — the same dict `options_flow_spec.md` defines and validates.
- Scope: the top-level option groups as they exist today (`rooms`, `reactions`, `learning`,
  `notifications`, `security`, `calendar`, `external_context`, `people_named`, `language`,
  `anomaly*`, etc. — see `const.py` for the current key set).
- Explicitly out of scope: anything that isn't `options` — event store, snapshots, proposals,
  approval records, and other runtime/derived state. Those are operational state, not
  configuration, and already have dedicated tooling (`scripts/diagnostics.py`,
  `scripts/ops_audit.py`). Conflating them into an "export" would produce a huge, mostly
  non-editable dump and defeat the bulk-editing purpose.

## Import

- Input: a YAML document with the same shape as the export output.
- **Validation must reuse the Options Flow's own validation — never a separate, looser path.**
  Concretely: the same per-field/per-step validators the Options Flow steps already apply, plus
  the structural installation check already exposed via
  `HeimaCoordinator.async_validate_config()` / `build_validation_report()`.
- **All-or-nothing.** An invalid import is rejected wholesale, with the same error reporting shape
  the Options Flow already uses. No partial apply.
- On success, an import behaves exactly as if an installer had walked the Options Flow and saved:
  it goes through the same structural-vs-runtime key handling already defined by
  `STRUCTURAL_OPTION_KEYS` (full entry reload for structural keys, `async_reload_options()` for
  runtime keys).
- Import is an installer-only, admin-authenticated action — same trust boundary as the Options
  Flow itself. Residents never see or use this.

## Format

- Plain YAML mirroring the `options` dict structure — no custom DSL, no templating.
- No new external dependency: PyYAML is already a transitive Home Assistant dependency (confirmed
  in the installed environment), consistent with the "core stays dependency-free" rule — this adds
  no new requirement.
- Comments: YAML supports them, and an installer may want to annotate their exported file. Export
  does not need to preserve any prior comments (HA's stored options are plain data with no comment
  concept), and this spec makes no promise of round-tripping comments through an export → edit →
  import cycle. This should be stated to installers so expectations are correct.

## Open questions (need a developer decision before this spec can be marked ready for implementation)

1. **Trigger surface.** A Home Assistant service (`heima.export_options` / `heima.import_options`,
   following the existing `SERVICE_*` convention in `services.py`), a CLI script under `scripts/`
   (consistent with `patch_heima_dev_options.sh` and the `ha_client.py` REST client used by other
   scripts), an admin-panel action once the admin panel (`panel.py`, in progress) supports it — or
   more than one of these? They aren't mutually exclusive, but v1 scope should be explicit.
2. **Full replace vs. partial merge on import.** Should import always replace the entire `options`
   dict, or support merging only the keys present in the YAML (closer to
   `patch_heima_dev_options.sh`'s merge-patch behavior)? Full replace is simpler to validate
   correctly; partial merge is more convenient for small tweaks but reintroduces some of the
   "what's the actual resulting state" ambiguity this spec is trying to avoid.
3. **Format/schema versioning.** There is no existing "options schema version" field precedent in
   the codebase — `options_migration.py` detects legacy shapes ad hoc rather than reading a version
   marker. Should export/import introduce one (to let a future schema change detect and reject a
   stale export), or continue the existing ad-hoc-migration pattern applied to imported YAML the
   same way it already is to stored options?
4. **Where the file lives.** Downloaded/uploaded only (browser or CLI, never persisted by Heima
   itself), or also optionally written to a fixed path under HA's `config/` for installers who want
   a tracked-in-git working copy?

## Acceptance Criteria

To be finalized once the open questions above are resolved. Draft baseline:

- Export produces a YAML file that, fed back into import unchanged, results in no configuration
  change (round-trip stability).
- Import of a YAML file with a deliberately invalid field is rejected with a field-level error
  message equivalent to what the Options Flow would show for the same invalid input, and leaves
  the existing configuration untouched.
- Import of a valid, modified YAML file produces the same runtime state (reload vs. hot-update
  behavior per `STRUCTURAL_OPTION_KEYS`) as making the equivalent change through the Options Flow.
- No YAML file is read at HA startup or integration setup under any circumstance.
