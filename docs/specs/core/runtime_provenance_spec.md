# Runtime Provenance Spec

**Status:** Draft vNext
**Date:** 2026-08-18
**Scope:** Runtime action provenance, apply-step ownership, admin/resident/system boundaries,
manual-hold ownership classification, recovery authorization, observability grouping
**Related specs:** `core/apply_step_contract.md`, `core/manual_hold_framework_spec.md`,
`core/runtime_checkpoint_and_power_recovery_spec.md`,
`core/resident_runtime_confirmation_spec.md`, `core/admin_observability_panel_spec.md`,
`core/reaction_identity_spec.md`, `core/event_catalog_spec.md`

## Purpose

Heima currently carries runtime provenance through several partial mechanisms:

- `ApplyStep.source`, usually `reaction:<reaction_id>`;
- `ApplyStep.context_id`, used as Home Assistant service-call correlation where supported;
- `ScriptApplyBatch`, which records short-lived script apply provenance;
- `PendingApply`, used by Manual Hold to classify state changes as Heima-owned or external;
- persisted reaction metadata such as `origin`, `author_kind`, `source_proposal_id`,
  `source_template_id`, `source_request`, and `admin_authored_template_id`;
- admin websocket boundaries guarded by Home Assistant admin checks;
- runtime confirmation requests that distinguish approved, dismissed, and timeout outcomes.

These mechanisms overlap but do not provide one authoritative runtime contract. This spec defines a
single runtime provenance model by evolving the existing `ApplyStep.source` field from a free-form
string into a structured source contract. It must not add a parallel `ApplyStep.provenance` field.

Normative rule:

> Authorization decisions must never be based on free-form provenance strings read from persisted
> config, proposal payloads, notification payloads, or user-controlled data.

## Goals

1. Represent who or what produced each runtime action.
2. Keep reaction/domain/admin/resident/system actions distinguishable at apply time.
3. Let recovery and other safety filters allow only actions from authoritative runtime boundaries.
4. Let Manual Hold classify Heima-owned state changes without parsing free-form strings.
5. Let observability group and explain actions from structured provenance.
6. Preserve backwards compatibility while migrating existing `ApplyStep.source` consumers.

## Non-Goals

- Replacing Home Assistant's permission model.
- Persisting a full audit log of every action.
- Making every Home Assistant service call attributable to a human user.
- Trusting mobile-app notification payloads as identity proof.
- Removing existing reaction metadata fields that describe persisted configuration.

## Existing Overlap And Target Relationship

| Existing mechanism | Current role | Target relationship |
|---|---|---|
| `ApplyStep.source` | Free-form runtime source, commonly `reaction:<id>`. Used by engine, observability, manual hold. | Evolve into a structured source object while accepting legacy strings during migration. New authorization must use helper-normalized structured source semantics. |
| `ApplyStep.context_id` | Optional Home Assistant `Context` id for service-call correlation. | Keep as HA correlation only. It is not semantic provenance. |
| `ScriptApplyBatch` | Runtime-local script provenance with source/reaction fields. | Derive from structured `ApplyStep.source`; keep script-specific fields where needed. |
| `PendingApply` | Manual-hold ownership marker for expected Heima-owned state changes. | Derive source reaction/id/type from structured `ApplyStep.source`. |
| Reaction metadata (`origin`, `author_kind`, `source_template_id`, ...) | Persisted configuration/proposal lineage. | Keep unchanged. It describes the saved reaction, not a specific runtime apply. |
| Runtime confirmation request status | Distinguishes approved/timeout/dismissed request outcomes. | Runtime application of stored steps gets `resident_response` or `timeout` provenance assigned by the controller/engine boundary. |
| Websocket admin actions | Admin-gated operations with `require_admin` and `connection.user.is_admin`. | Admin-command provenance may be assigned only at this boundary or another equivalent HA-admin-verified boundary. |

## Codebase Verification

Current direct `ApplyStep.source` consumers are concentrated and migratable:

- `engine._reaction_from_step_source(...)` parses `reaction:<id>` with `startswith`/`split`;
- engine reaction dispatch tags steps with `source=f"reaction:{reaction_id}"`;
- recovery currently checks `source` strings to distinguish reaction vs non-reaction steps;
- Manual Hold pending applies parse `source` to derive `source_reaction_id`;
- runtime observability groups steps through `_reaction_id_from_source(step.source)`;
- diagnostics/logging expose `step.source`;
- tests assert the legacy `reaction:<id>` string.

Therefore implementation should reuse `source` instead of adding another field. Some consumers still
need changes because they parse strings directly, but the migration is small and centralized:
replace direct parsing with helper functions that accept both legacy strings and structured source
objects.

## Core Contract

### ApplyStepSource

Every new runtime-created `ApplyStep` should carry structured source information in the existing
`source` field:

```python
@dataclass(frozen=True)
class ApplyStepSource:
    kind: ApplyStepSourceKind
    source_id: str
    source_type: str | None = None
    actor_type: ApplyStepSourceActorType = "heima"
    actor_id: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid4()))

    def legacy_key(self) -> str:
        ...
```

Closed vocabularies:

```python
ApplyStepSourceKind = Literal[
    "reaction",
    "domain",
    "admin_command",
    "resident_response",
    "timeout",
    "recovery",
    "system",
    "test",
    "legacy",
]

ApplyStepSourceActorType = Literal[
    "ha_admin",
    "resident",
    "heima",
    "scheduler",
    "service",
    "system",
    "test",
    "unknown",
]
```

Field meaning:

- `kind`: runtime path that produced this action.
- `source_id`: stable id of the source within that path. Examples: reaction id, domain id,
  websocket action id, request id.
- `source_type`: optional type/family. Examples: reaction type, domain name, admin action name.
- `actor_type`: class of actor that authorized or produced the action.
- `actor_id`: HA user id, recipient id, service id, or `null` when unavailable or intentionally
  redacted.
- `correlation_id`: runtime-local id used to connect apply steps, pending applies, script batches,
  observability traces, and service-call context where possible.
- `legacy_key()`: deterministic compatibility rendering. For example, reaction source renders as
  `reaction:<source_id>`.

### Trust Is Derived, Not Stored

There must be no persisted or user-writable `trusted` field.

Authoritativeness is derived by code from the boundary that assigned structured source. For example:

- a configured reaction loaded from options can produce `kind="reaction"`, but cannot declare
  itself to be an admin command;
- a websocket admin action can produce `kind="admin_command"` only after Home Assistant confirms the
  connection user is admin;
- a runtime confirmation timeout can produce `kind="timeout"` only from the in-process timeout
  controller;
- a resident mobile-app response can produce `kind="resident_response"` only after matching an
  active runtime confirmation request id.

Any source data read from persisted config, proposal payloads, imported YAML/JSON, notification
payloads, or legacy fields is non-authoritative until a runtime boundary reassigns or validates it.

Suggested helper:

```python
def is_authoritative_provenance(
    source: ApplyStepSource | str,
    *,
    required_kind: ApplyStepSourceKind,
) -> bool:
    ...
```

The implementation may encode boundary knowledge internally. It must not return `True` because an
untrusted payload contains a matching string.

## ApplyStep Integration

Target `ApplyStep` shape:

```python
@dataclass(frozen=True)
class ApplyStep:
    domain: str
    target: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    blocked_by: str = ""
    source: ApplyStepSource | str = ""  # structured source, legacy string during migration
    context_id: str | None = None
    step_id: str = ""
    depends_on: tuple[str, ...] = ()
    recovery_policy: RecoveryApplyPolicy = "block"
```

Migration rule:

- New runtime code should set `source` to `ApplyStepSource`.
- Legacy runtime code may continue to set `source` to a string temporarily.
- Structured source should render to legacy form where practical:
  - `kind="reaction"` -> `source="reaction:<source_id>"`;
  - `kind="domain"` -> `source="domain:<source_id>"`;
  - other kinds may keep `source` empty or use a diagnostic value.
- Consumers must access `source` through helpers such as `step_source_kind(step)`,
  `step_source_id(step)`, `step_source_legacy_key(step)`, and
  `reaction_id_from_step_source(step)`.
- Direct string parsing (`startswith`, `split`, ad hoc prefixes) is legacy code and should be
  removed from authorization paths first.
- Builders that rehydrate `ApplyStep(**raw)` from persisted config must sanitize any raw structured
  `source` mapping. Persisted config may provide only legacy, non-authoritative source hints until a
  runtime boundary replaces them.

## Boundary Rules

### Reaction Runtime Boundary

Reaction implementations may continue to return plain `ApplyStep` instances without authoritative
reaction source.

The engine's reaction dispatch boundary is responsible for tagging returned steps with:

```text
kind=reaction
source_id=<reaction_id>
source_type=<reaction_type>
actor_type=heima
```

This preserves the current pattern where the engine already sets `source="reaction:<id>"` after
`reaction.evaluate(...)`.

### Domain Runtime Boundary

Domain-generated apply steps, such as lighting and heating domain steps, should get:

```text
kind=domain
source_id=<domain_id>
source_type=<domain_family>
actor_type=heima
```

This lets observability distinguish domain pipeline actions from reaction actions without relying on
empty `source` fallback behavior.

### Admin Command Boundary

`kind="admin_command"` may be assigned only by a Home Assistant admin-verified boundary.

Allowed AS boundary:

- websocket commands protected by `websocket_api.require_admin` and an explicit
  `connection.user.is_admin` check.

Service calls must not produce authoritative `admin_command` source in AS. They may produce
`kind="service"` if a future vocabulary extension needs it, or no apply-step source at all when the
service does not create apply steps. A future phase may allow service calls to produce
`admin_command` only after explicit HA-admin verification from `ServiceCall.context.user_id` or an
equivalent HA-supported permission check.

### Resident Response Boundary

`kind="resident_response"` may be assigned only when:

- a mobile-app action response references an active runtime confirmation request;
- the request is successfully claimed for processing;
- the response action is supported for that request.

Mobile notification payloads are routing data, not identity proof. If Home Assistant exposes a user
or device id for the event, it may be copied into `actor_id` for diagnostics, but it must not be used
as an authorization guarantee unless separately verified.

### Timeout Boundary

`kind="timeout"` may be assigned only by the runtime confirmation timeout controller when
`on_timeout="apply"` and the active request is successfully claimed.

Timeout-applied steps must never count as resident approval for promotion logic, per
`core/resident_runtime_confirmation_spec.md`.

### Recovery/System/Test Boundaries

`kind="recovery"` and `kind="system"` are reserved for engine-owned runtime facilities.

`kind="test"` is allowed only in tests and live-test harnesses. Production code must not branch on
`test` except for diagnostics or explicit test-only helpers.

## Recovery Authorization

Recovery filtering must not authorize bypasses from free-form `ApplyStep.source` strings.

For example, `recovery_policy="allow_admin_command"` is valid only when:

```text
step_source_kind(step) == "admin_command"
and is_authoritative_provenance(step.source, required_kind="admin_command")
```

`recovery_policy="allow_when_inputs_stable"` remains domain-specific. For camera privacy policies,
the recovery filter may still require:

- source reaction type/config matches `security.camera_privacy_policy`;
- security state is not `unknown`/`unavailable`;
- target is one of the configured camera privacy switches.

Those checks should use structured source where available and fall back to legacy source/config
only during migration.

## Manual Hold Integration

Manual Hold should derive pending apply ownership from structured `ApplyStep.source`.

Target `PendingApply` source fields:

```python
source_kind: ApplyStepSourceKind
source_id: str | None
source_type: str | None
correlation_id: str
```

Compatibility:

- `source_reaction_id` and `source_reaction_type` may remain as diagnostics during migration.
- They should be derived from structured source when `kind="reaction"`.
- Manual Hold classification must continue to consume pending applies by entity/expected state and
  TTL; structured source explains ownership, but does not replace the expected-state match.

## Script Apply Batch Integration

`ScriptApplyBatch` should be reduced to script-specific apply metadata plus shared structured source:

```python
@dataclass(frozen=True)
class ScriptApplyBatch:
    script_entity: str
    applied_ts: float
    source: ApplyStepSource
    expected_domains: tuple[str, ...] = ()
    expected_subject_ids: tuple[str, ...] = ()
    expected_entity_ids: tuple[str, ...] = ()
```

Compatibility fields (`source_legacy`, `origin_reaction_id`, `origin_reaction_type`,
`correlation_id`) may remain in diagnostics as derived values while consumers migrate.

## Observability Integration

Decision traces and activity events should group apply steps by structured source:

- `kind="reaction"` -> group id `reaction:<source_id>`;
- `kind="domain"` -> group id `domain:<source_id>`;
- `kind="admin_command"` -> group id `admin_command:<source_id>`;
- `kind="resident_response"` -> group id `runtime_confirmation:<source_id>`;
- otherwise `kind:<source_id-or-correlation_id>`.

The legacy `_reaction_id_from_source(step.source)` fallback remains only for string sources or
structured sources whose kind is `legacy`.

Observability should expose structured source in step diagnostics with secrets redacted:

```yaml
source:
  kind: reaction
  source_id: camera_privacy_policy__interna__armed_night__any__turn_off
  source_type: alarm_state_action
  actor_type: heima
  actor_id: null
  correlation_id: ...
```

## Persistence And Imports

Persisted reaction config may contain reaction metadata and legacy source hints, but must not contain
authoritative runtime source objects.

If an import/config payload includes structured `source`, the normalizer must either:

- drop it; or
- keep it under a diagnostic/import namespace that cannot affect runtime authorization.

No user-editable config field may cause Heima to create `admin_command`, `resident_response`,
`timeout`, `recovery`, or `system` authoritative provenance.

### Actor Redaction

Raw `actor_id` values may exist only in runtime memory.

Diagnostics, admin observability exports, logs, checkpoints, and persisted stores must expose only
redacted actor identifiers. AS uses stable hashes without display names:

```yaml
actor_id: ha_user:sha256:<short_hash>
```

This keeps repeated actions attributable to the same actor for debugging without exposing the raw HA
user id or mobile-device identifier.

## Backward Compatibility

The migration should be staged:

1. Add `ApplyStepSource` and helper constructors.
2. Change `ApplyStep.source` type to `ApplyStepSource | str`, preserving legacy string support.
3. Update engine reaction dispatch to assign structured reaction source.
4. Update domain apply-step builders to assign structured domain source.
5. Update runtime confirmation application to assign resident-response/timeout source when
   applying stored steps.
6. Update Manual Hold pending applies and `ScriptApplyBatch` to derive from structured source.
7. Update observability grouping and diagnostics to prefer structured source with legacy fallback.
8. Update recovery authorization so `allow_admin_command` requires authoritative admin-command
   source.
9. After all production builders are migrated, fail tests when non-test apply steps reach the apply
   layer with `kind="legacy"`.

Post-AS target:

- production builders emit `ApplyStepSource`;
- helper functions continue accepting legacy strings at compatibility/import/test boundaries;
- legacy strings are never authoritative and cannot bypass recovery or other safety filters.

## Acceptance Criteria

- No recovery authorization decision depends on parsing `ApplyStep.source`.
- Config/import payloads cannot self-authorize as admin/system/recovery/resident source.
- Existing reaction grouping remains stable during migration.
- Manual Hold still correctly classifies Heima-owned vs external state changes.
- Runtime confirmation approval and timeout paths carry distinct source.
- Observability shows structured source for apply steps and keeps legacy string rendering for
  migration.
- Unit tests cover forged persisted source and prove it cannot bypass recovery.
- Unit tests cover reaction, domain, admin-command, resident-response, timeout, and legacy
  source paths.

## Resolved Decisions

1. AS assigns authoritative `admin_command` source only from websocket/admin-panel actions guarded by
   Home Assistant admin checks. Service calls are not authoritative admin commands in AS.
2. Raw `actor_id` is runtime-memory-only. Diagnostics, observability, logs, checkpoints, and stores
   expose stable hashed actor ids.
3. `ApplyStep.source` remains `ApplyStepSource | str` through AS. Production builders must migrate
   to `ApplyStepSource`; legacy strings remain compatibility-only and never authoritative.
