# Signal Discovery Pipeline Spec

**Status:** Draft v1.0 — Phase V
**Related:**
- `learning/canonical_signal_pipeline_spec.md` — canonical signal contract and EventCanonicalizer
- `learning/learning_system_spec.md` — event store, analyzers, proposals
- `core/options_flow_spec.md` — options structure (`rooms[*].signals`, `rooms[*].learning_sources`)

---

## Problem

The canonical signal pipeline (Phase C/canonical_signal_pipeline_spec.md) defines how signals
are normalized and canonicalized at runtime. However, signals must be manually added to
`rooms[*].signals` or `rooms[*].learning_sources` by the installer through the config flow.

There is no mechanism to discover signals that are already present in HA but not yet tracked.
As a result, useful context signals (lux, CO2, humidity, media players) are silently ignored
until the installer explicitly configures them.

---

## Principle

> Heima classifies all HA entities heuristically, proposes relevant ones to the installer,
> and only tracks them after explicit approval. Classification is automatic; use is not.

The pipeline does not add a second normalization path. It produces configuration patches
that feed into the existing EventCanonicalizer and learning_sources. The runtime is unchanged.

---

## Scope

### v2 (this spec)
- Inventory of all HA entities by reading entity registry and current states once.
- Rule-based classification using `domain`, `device_class`, `unit_of_measurement`, HA area.
- Room mapping via HA area → Heima room_id (name-based heuristic).
- Suggestion proposal via the existing `ProposalEngine` (same pattern as semantic policies,
  Phase N).
- Options patch on acceptance: additive merge into `rooms[*].signals` or
  `rooms[*].learning_sources`.
- Coordinator auto-applies accepted signal discovery patches via `async_update_entry`.
- Trigger: coordinator startup + `EVENT_ENTITY_REGISTRY_UPDATED`.

### v3 (deferred — not in this spec)
- Plugin/registry API for third-party signal classifiers (e.g. solar, energy packs).
- `ISignalClassifier`, `ICanonicalSignalContract`, `IPromotionTarget` extension points.
- Multi-room signals and per-entity override of bucket config.
- Discovery based on state history, entropy, or correlation with occupancy/house_state.
- Unmatched-room suggestions (requires room assignment UI).

---

## Pipeline Overview

```
HA entity registry + states
     │
     ▼
SignalDiscoveryAudit.run()
  - reads all entities once
  - filters by supported domain/device_class
  - maps entity → Heima room via area heuristic
  - produces SignalSuggestion per matched entity
     │
     ▼
_async_evaluate_signal_discovery()  [coordinator]
  - for each suggestion: submit to ProposalEngine if not already proposed
  - fire installer alert notification (same pattern as Phase N)
     │
     ▼
installer accepts proposal
     │
     ▼
_async_apply_accepted_signal_patches()  [coordinator]
  - reads accepted signal_discovery proposals
  - applies additive merge to options
  - calls async_update_entry → coordinator reload
     │
     ▼
EventCanonicalizer picks up new signals naturally on reload
```

---

## Data Model

### `HAEntityDescriptor`

Read-only descriptor built from HA entity registry + state.

```python
@dataclass(frozen=True)
class HAEntityDescriptor:
    entity_id: str
    domain: str                         # "sensor", "media_player", …
    device_class: str | None
    unit_of_measurement: str | None
    area_id: str | None                 # HA area_id, if assigned
    area_name: str | None               # HA area display name
    current_state: str | None
```

### `SignalSuggestion`

Classification output for one entity. Not persisted — regenerated on each audit run.

```python
@dataclass
class SignalSuggestion:
    suggestion_id: str                  # uuid4, for tracing
    entity_id: str
    room_id: str                        # Heima room_id resolved via room mapping
    role: Literal["room_signal", "learning_source"]
    signal_name: str | None             # "room_lux", "room_co2", "room_humidity" — None for learning_source
    device_class: str | None
    confidence: float                   # 0.0–1.0
    evidence: list[str]                 # human-readable reasons
    options_patch: SignalOptionsPatch
    identity_key: str                   # "signal_discovery:{entity_id}"
```

### `SignalOptionsPatch`

Concrete, typed description of what to add to options on approval.

```python
@dataclass
class SignalOptionsPatch:
    room_id: str
    role: Literal["room_signal", "learning_source"]
    # For role == "room_signal": full signal config as per canonical_signal_pipeline_spec.md
    # For role == "learning_source": {"entity_id": "..."}
    payload: dict[str, Any]
```

---

## Classification Rules

Classification is purely rule-based. No ML, no statistics, no EventStore queries.
Evaluated once per entity at audit time.

### Supported signal classes

| domain | device_class | role | signal_name | confidence |
|---|---|---|---|---|
| `sensor` | `illuminance` | `room_signal` | `room_lux` | 0.95 |
| `sensor` | `carbon_dioxide` | `room_signal` | `room_co2` | 0.95 |
| `sensor` | `humidity` | `room_signal` | `room_humidity` | 0.90 |
| `media_player` | any | `learning_source` | — | 0.80 |

Entities not matching any row are silently ignored. No "unknown" suggestions are generated.

### Evidence population (examples)

```
["device_class=illuminance", "unit=lx", "area=Studio", "matched room: studio"]
["domain=media_player", "area=Salone", "matched room: salone"]
```

### Default bucket config by signal class

Applied when building `options_patch.payload` for `room_signal` suggestions.

| signal_name | Buckets |
|---|---|
| `room_lux` | dark: 30, dim: 100, ok: 300, bright: null |
| `room_co2` | ok: 800, elevated: 1200, high: null |
| `room_humidity` | low: 40, ok: 70, high: null |

Bucket boundaries follow the canonical upper-exclusive convention defined in
`canonical_signal_pipeline_spec.md §Signal configuration`.

---

## Room Mapping Algorithm

Entities that cannot be mapped to a Heima room are dropped silently.
No unmatched-room suggestions are generated in v2.

```
1. entity has HA area_id?
   no → SKIP entity

2. read HA area display name (area_name, lowercased, stripped)

3. for each room in options["rooms"]:
     room_id_norm = room_id.lower().replace("_", " ")
     if area_name == room_id_norm → MATCH (exact)
     if area_name in room_id_norm OR room_id_norm in area_name → MATCH (substring)

4. exactly one match? → use its room_id
   zero matches → SKIP entity
   multiple matches → use longest room_id_norm match; on tie, SKIP
```

Evidence line added on match: `"matched room: {room_id} (area: {area_name})"`.

---

## Options Patch Semantics

Patches are always **additive**. Existing signals or learning sources are never modified
or removed. If a conflict is detected, the patch is skipped silently.

### `room_signal` patch

Payload structure mirrors `rooms[*].signals[*]` from `canonical_signal_pipeline_spec.md`:

```json
{
  "signal_name": "room_lux",
  "entity_id": "sensor.lux_studio",
  "device_class": "illuminance",
  "buckets": [
    {"label": "dark", "upper_bound": 30},
    {"label": "dim",  "upper_bound": 100},
    {"label": "ok",   "upper_bound": 300},
    {"label": "bright", "upper_bound": null}
  ]
}
```

**Merge algorithm:**
```
1. find room in options["rooms"] where room["room_id"] == patch.room_id
   not found → abort patch (room may have been deleted)

2. existing = [s for s in room.get("signals", []) if s["signal_name"] == patch.signal_name]
   existing non-empty → SKIP (signal already configured — do not overwrite installer choice)

3. append payload to room["signals"]
```

### `learning_source` patch

Payload structure:
```json
{"entity_id": "media_player.tv_salone"}
```

**Merge algorithm:**
```
1. find room in options["rooms"] where room["room_id"] == patch.room_id
   not found → abort patch

2. sources = room.get("learning_sources", [])
   patch.payload["entity_id"] already in sources → SKIP

3. append entity_id to room["learning_sources"]
```

---

## Proposal Lifecycle

Signal suggestions are surfaced via the existing `ProposalEngine`, using the same
pattern as semantic policy suggestions (Phase N).

### Proposal type

Each suggestion is submitted as `ReactionProposal` with:

| field | value |
|---|---|
| `analyzer_id` | `"signal_discovery"` |
| `reaction_type` | `"signal_discovery"` |
| `origin` | `"admin_authored"` |
| `followup_kind` | `"config_suggestion"` |
| `identity_key` | `"signal_discovery:{entity_id}"` |
| `confidence` | `suggestion.confidence` |
| `description` | human-readable summary of the suggestion |
| `suggested_reaction_config` | serialized `SignalOptionsPatch` |

### Deduplication

If `proposal_by_identity_key(identity_key)` returns any non-None result (pending, accepted,
or rejected), the suggestion is not resubmitted.

Rationale: once an installer has acted on a suggestion (accepted or rejected), the discovery
system respects that decision and does not re-surface the same entity.

### Installer notification

For each newly submitted proposal, fire a persistent HA notification:

```
notification_id: "heima_installer_signal_discovery_{entity_id_slug}"
title: "Heima: new signal candidate"
message: "Entity {entity_id} detected as {signal_name or 'learning source'} for room '{room_id}'. Confidence: {confidence:.0%}."
```

`entity_id_slug`: entity_id with `.` replaced by `_`.

Same deduplication pattern as Phase N: track submitted notification keys in
`coordinator._notified_installer_alert_keys` to avoid repeat notifications.

### Accept routing

Signal discovery proposals are **not** regular reactions. When accepted, they must not be
added to `options["reactions"]["configured"]`.

There are two entry points where acceptance can occur. Both must guard against the
signal_discovery path.

**Entry point 1 — `heima.approve_proposal` service**

The service handler calls `coordinator.async_review_proposal()`. This method currently
dispatches on proposal type:

```python
# coordinator.py — async_review_proposal()
if proposal_type == HOUSE_STATE_PROPOSAL_TYPE:  → async_review_house_state_proposal()
if proposal_type == ACTIVITY_PROPOSAL_TYPE:      → async_review_activity_proposal()
# else: return False  ← signal_discovery would silently fail here today
```

A new branch must be added:

```python
if proposal.analyzer_id == "signal_discovery":
    return await self.async_review_signal_discovery_proposal(
        proposal_id, decision=decision
    )
```

`async_review_signal_discovery_proposal()` calls `proposal_engine.async_accept_proposal()`
or `async_reject_proposal()` and does nothing else — the actual options patch is applied
lazily by `_async_apply_accepted_signal_patches()` on the next coordinator cycle.

**Entry point 2 — config flow `_steps_reaction_proposals.py`**

The config flow's proposal review step (line ~180) calls
`coordinator.proposal_engine.async_accept_proposal(current_id)` and then writes to
`options["reactions"]["configured"]`. For signal_discovery proposals this write must be
skipped:

```python
# Before adding to reactions["configured"], guard:
if accepted_proposal.analyzer_id == "signal_discovery":
    # accept status already set; skip reaction config write
    return await self.async_step_proposals() if queue else ...

configured[target_id] = self._configured_reaction_from_proposal(...)
# ...
```

This guard applies to every config-flow path that can accept a proposal, including the
follow-up action-configuration path. A signal discovery proposal must short-circuit before
any call that builds configured reaction payloads, mutates `reactions["configured"]`, or
stores reaction labels.

No shared accept path exists between signal discovery and reaction proposals.

### Acceptance handler — `_async_apply_accepted_signal_patches()`

Called at the end of each coordinator cycle (after `_async_evaluate_signal_discovery()`).

"Already applied" is determined by inspecting current options, not by in-memory tracking.
This is idempotent across coordinator restarts and handles the case where the patch was
accepted but the coordinator crashed before applying it.

```
1. for each accepted ReactionProposal where analyzer_id == "signal_discovery":

2. deserialize SignalOptionsPatch from proposal.suggested_reaction_config

3. check if patch is already reflected in current options:
     role == "room_signal":
       room = find room by room_id in options["rooms"]
       signal already in room["signals"] by signal_name? → SKIP (idempotent)
     role == "learning_source":
       room = find room by room_id in options["rooms"]
       entity_id already in room.get("learning_sources", [])? → SKIP (idempotent)

4. apply additive merge to options (in-memory copy)

5. await async_update_entry(entry, options=patched_options)
   break  (one patch per cycle to avoid thundering-herd on reload)
```

No `_applied_signal_patch_ids` field is needed. The options state itself is the
idempotency guard.

---

## Trigger Timing

Signal discovery is not part of the hot evaluation cycle.

| Trigger | Action |
|---|---|
| Coordinator startup (`async_initialize`) | Run `SignalDiscoveryAudit.run()` once |
| `EVENT_ENTITY_REGISTRY_UPDATED` | Schedule audit via `async_call_later(0, ...)` |

The audit reads entity registry + states from HA in-memory — no blocking I/O, no EventStore.
Suggestions are evaluated in `_async_evaluate_signal_discovery()` at the next coordinator
cycle after the audit completes.

---

## `SignalDiscoveryAudit`

Stateless, called from the coordinator. Receives the HA entity registry and current states.

```python
class SignalDiscoveryAudit:
    def run(
        self,
        entity_descriptors: Iterable[HAEntityDescriptor],
        heima_rooms: list[dict[str, Any]],
    ) -> list[SignalSuggestion]:
        """Classify entities and return one suggestion per matched entity."""
        ...
```

Input `heima_rooms` is `entry.options.get("rooms", [])`.

Maximum 50 suggestions per run. If more than 50 entities match, the first 50 by
`entity_id` alphabetical order are returned. This prevents proposal store saturation
in large installations.

---

## Coordinator Integration

### New fields
```python
coordinator._pending_signal_suggestions: list[SignalSuggestion]  # populated by audit
```

### New methods
```python
async def _async_evaluate_signal_discovery(self) -> None:
    """Submit new suggestions to ProposalEngine and fire installer alerts."""
    ...

async def _async_apply_accepted_signal_patches(self) -> None:
    """Apply one accepted patch per cycle, reload options if changed."""
    ...
```

### Call order in coordinator cycle
```
existing cycle
  ...
  await self._async_evaluate_semantic_policies()
  await self._async_evaluate_signal_discovery()   # new
  await self._async_apply_accepted_signal_patches()  # new
  ...
```

---

## Privacy and Performance Constraints

- Entity registry read is one HA in-memory call — not a network call, not blocking I/O.
- No entity state history is read or stored.
- No raw HA state values enter the EventStore.
- Audit result (`list[SignalSuggestion]`) is not persisted — regenerated from scratch on
  each trigger. Persistence is the ProposalEngine's responsibility (via `identity_key`).
- Entities in domains not listed in the classification table are ignored entirely — Heima
  does not store a catalogue of all HA entities.

---

## Post-implementation Invariants

1. Signal discovery never adds a second normalization path — it only produces options patches.
2. `EventCanonicalizer` is the only runtime normalizer. It reads from `options["rooms"][*].signals`
   which may have grown via accepted patches.
3. `rooms[*].signals[*].signal_name` is unique per room — enforced by the merge algorithm
   (same signal_name → skip).
4. `rooms[*].learning_sources` entries are unique per room — enforced by the merge algorithm
   (same entity_id → skip).
5. Once an installer rejects a signal suggestion, that entity is not re-proposed unless the
   rejected proposal is manually cleared.
6. Options patches are applied at most one per coordinator cycle to prevent thundering-herd
   on coordinator reload.
7. The audit runs outside the hot evaluation cycle — never called from `infer()` or domain
   evaluation methods.
