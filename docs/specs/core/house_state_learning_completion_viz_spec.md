# House State Learning Completion Visualization — Admin UI Spec

**Status:** Planned — approved after design discussion; not yet phased/numbered, not implemented.  
**Target:** UI enhancement for house state learning observability  
**Related:** `HouseStateInferenceModule` (`inference/modules/house_state_inference.py`), `ApprovalStore` (`inference/approval_store.py`), `ProposalEngine` (`runtime/proposal_engine.py`)  
**Last Updated:** 2026-08-26

---

## 1. Purpose

Provide **at-a-glance visibility** into which **house-state patterns** the system has learned across the **7×24 weekly schedule** (7 weekdays × 24 hour buckets). This addresses:

- **Gap identification**: Quickly spot unlearned time slots (e.g., missing weekend data)
- **Correctness validation**: Verify expected patterns (e.g., "working" at 9 AM on weekdays)
- **Debugging**: Identify anomalous learned states (e.g., "away" at 3 AM)
- **Proposal management**: Remove accepted proposals that are no longer valid

---

## 2. Data Contract

### 2.1 Data Source: HouseStateInferenceModule

**Module:** `HouseStateInferenceModule` (`custom_components/heima/runtime/inference/modules/house_state_inference.py`)

**Why HouseStateInferenceModule instead of WeekdayStateModule:**
- HouseStateInferenceModule generates **learning proposals** that users can accept/reject
- Accepted proposals are stored in `ApprovalStore` and synchronized via `sync_approval_state()`
- `HouseStateInferenceModule.diagnostics()` already exposes `approved_model_entries` with full context
- Each approved entry has a `context_key` containing `weekday`, `hour_bucket`, `rooms`, `anyone_home`, `predicted_state`

### 2.2 Required Data from `HouseStateInferenceModule.diagnostics()`

```python
{
    "module_id": "house_state_inference",
    "ready": bool,
    "slot_count": int,
    "tiers": {
        "rich": {...},
        "coarse": {...},
        "minimal": {...}
    },
    "approved_context_keys": int,  # count of accepted proposals
    "rejected_context_keys": int,  # count of rejected proposals
    "analyzed_snapshots": int,
    "approved_model_entries": [   # <-- Key data for visualization
        {
            "tier": str,              # "rich", "coarse", or "minimal"
            "context_key": str,        # e.g. "weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:...:state:working"
            "context_snapshot": {
                "weekday": int,          # 0-6 (0=Monday)
                "hour_bucket": int,      # 0-23
                "rooms": list[str],      # e.g. ["living"]
                "anyone_home": bool,
                "predicted_state": str,  # e.g. "working"
                "learning_context": dict
            },
            "predicted_state": str,
            "count": int,             # observations for this state
            "total": int,             # total observations for this context
            "confidence": float      # P(predicted_state | context)
        },
        ...
    ],
    "min_support": int,
    "rich_min_support": int,
    "minimal_min_support": int,
    "confidence_threshold": float
}
```

**Verified against `_approved_model_entries_diagnostics()`
(`house_state_inference.py:242-259`): this is the complete, exact set of keys per entry.
`context_snapshot` is built by `house_state_context_snapshot()` (`approval_store.py:198-215`) and
always normalizes `rooms` to a genuine `list[str]`, regardless of what container type was passed
in when the key was built.**

**Important — no `proposal_id` here.** Unlike the rest of the fields above, `proposal_id` is
**not** present anywhere in `approved_model_entries`, and no code path adds one. The "Remove
proposal" feature (§2.4, §3.4, §7) needs a `proposal_id` to call the existing review endpoint, so
it must be resolved separately — see §2.4.

### 2.3 Derived Slot Model

For visualization, we derive a **7×24 slot model** from `approved_model_entries`:

For each **(weekday, hour_bucket)** tuple (168 total):

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `slot_key` | string | `"weekday,hour_bucket"` | Unique identifier (e.g., `"1,8"` = Monday, 8 AM) |
| `proposals` | list | Filtered from `approved_model_entries` | All accepted proposals matching (weekday, hour_bucket) |
| `has_learned` | bool | `len(proposals) > 0` | True if any proposal exists for this slot |
| `states` | list[str] | From proposals | All learned states for this slot (may be multiple) |

**Note:** A single (weekday, hour_bucket) slot can have **multiple accepted proposals** because proposals are differentiated by `rooms`, `anyone_home`, and `learning_context`. For example:
- Monday 8 AM with people in living room -> "working"
- Monday 8 AM with empty house -> "away"

### 2.4 Proposal Removal Contract

**Resolving `proposal_id` (no backend change needed).** `approved_model_entries` doesn't carry a
`proposal_id`, but the admin observability snapshot already exposes the full proposal list
elsewhere, with everything needed to join by `context_key`:

- `snapshot.proposals.raw.proposals` — the verbatim `ProposalEngine.diagnostics()["proposals"]`
  list (`observability.py:915` stores the whole diagnostics dict under `"raw"`;
  `proposal_engine.py:1064-1099` is where each proposal dict, including `id`, `status`,
  `identity_key`, is built). This is **already reaching the frontend** on every snapshot load —
  not gated behind a new endpoint or a new field.
- For house-state proposals, `identity_key` is built as
  `f"{HOUSE_STATE_PROPOSAL_TYPE}:{context_key}"` where `HOUSE_STATE_PROPOSAL_TYPE =
  "house_state_learned_context"` (`approval_store.py:16`, set at `coordinator.py:2930`) — i.e.
  literally `"house_state_learned_context:" + context_key`.
- Resolution: for a given `approved_model_entries` entry's `context_key`, find the proposal in
  `snapshot.proposals.raw.proposals` whose `status === "accepted"` and whose `identity_key ===
  "house_state_learned_context:" + context_key`; that proposal's `id` is the `proposal_id` to use
  below. If no match is found (a rare race between the two data sources refreshing), the Remove
  button for that entry is disabled — see §7.

**Existing endpoint:** `heima/observability/action` with `action: "review_proposal"`

**Payload to remove an accepted proposal.** `_review_proposal` (`websocket_api.py:328-345`) reads
`proposal_id`/`decision` from `msg.get("payload")`, the same nested-`payload` convention every
other `heima/*/action` command in this codebase uses (`heima/topology/action`,
`heima/actuators/action`) — **not top-level message fields**:
```json
{
    "type": "heima/observability/action",
    "action": "review_proposal",
    "payload": {
        "proposal_id": "<proposal_id>",
        "decision": "rejected"
    }
}
```

**Flow:**
1. Frontend resolves `proposal_id` for the clicked entry per the join above.
2. Frontend calls WS endpoint with `payload: {proposal_id, decision: "rejected"}`.
3. `websocket_api.py:_review_proposal()` calls `coordinator.async_review_proposal(proposal_id,
   decision, approved_by)`.
4. `coordinator.async_review_proposal()` routes to `async_review_house_state_proposal()`.
5. Proposal status changes from "accepted" to "rejected".
6. `ApprovalStore` records the rejection.
7. `HouseStateInferenceModule.sync_approval_state()` updates `_approved_context_keys`.
8. Proposal is removed from inference and no longer affects house state resolution.

**Reference:**
- `websocket_api.py:224-236` (endpoint handler)
- `websocket_api.py:328-345` (`_review_proposal` function)
- `coordinator.py:742-768` (`async_review_proposal` dispatcher — takes `proposal_id`, `decision`,
  `approved_by`, not `context_key`)
- `coordinator.py:770-807` (`async_review_house_state_proposal`)

---

## 3. UI/UX Design

### 3.1 Primary View: 7×24 Matrix

**Layout:**
- **Rows:** 7 (Mon–Sun, ISO order: 0=Mon → 6=Sun)
- **Columns:** 24 (00–23, hour buckets)
- **Position:** New section in House State admin page (below existing metrics)

**Cell Content:**
- **Empty** (gray background, `#E0E0E0`) if no accepted proposals for this slot
- **Multiple states indicator** (amber background, `#FFEB3B`) if 2+ proposals exist for the slot, showing count (e.g., "2")
- **Single state abbreviation** (colored text) if exactly one proposal exists

**Visual Priority:**
When multiple states exist for one slot, show the count. On hover/tooltip, list all states.

**State Abbreviations & Colors:**

| State | Abbreviation | Color | Hex | Notes |
|-------|--------------|-------|-----|-------|
| `home` | H | Green | `#4CAF50` | Default/home base state |
| `working` | W | Orange | `#FF9800` | Active work time |
| `relax` | R | Blue | `#2196F3` | Calm/leisure time |
| `sleeping` | S | Purple | `#673AB7` | Rest period |
| `away` | A | Red | `#F44336` | House unoccupied |
| `guest` | G | Amber | `#FFC107` | Temporary visitors |
| `vacation` | V | Brown | `#795548` | Extended absence |
| *No proposals* | (empty) | Gray | `#E0E0E0` | Placeholder |

**Styling:**
- Cell size: `30px × 30px` (min-width to fit content)
- Font: Bold, centered
- Border: `1px solid #E0E0E0` (light gray grid lines)
- Hover: Background darkens by 10% + cursor pointer
- Multiple states: Background `#FFEB3B` (amber-100) to indicate complexity

### 3.2 Tooltips (on hover)

For **slots with proposals:**
```
[Day Name] [Hour]:00 - [State 1], [State 2], ...
[N] accepted proposal(s) for this slot
Click to view details and manage
```

Example:
```
Monday 08:00 - working
1 accepted proposal for this slot
Click to view details and manage
```

For **slots with multiple proposals:**
```
Monday 08:00 - working, away
2 accepted proposals for this slot
Click to view details and manage
```

For **empty slots:**
```
Saturday 03:00 - No learned patterns
No accepted proposals for this slot
```

### 3.3 Completion Index (Header)

**Text:** `"House State Learning: X slots with accepted proposals (Y%)"`
- `X` = Count of (weekday, hour_bucket) slots with >=1 accepted proposal
- `Y` = `(X / 168) * 100` (rounded to integer)

**Position:** Section header (above matrix)
**Style:** Bold, 16px, left-aligned

### 3.4 Detail View: Per-Slot Proposal Management

**Trigger:** Click on any cell in the matrix (learned or empty).

**Content:** Expandable section below the matrix showing all proposals for that (weekday, hour_bucket) slot:

```
=== [Day Name] [Hour]:00 — Proposal Management ===

| # | State | Rooms | Anyone Home | Confidence | Support | Proposal ID | Actions |
|---|-------|-------|-------------|------------|---------|------------|---------|
| 1 | working | living | Yes | 88% | 22/25 | abc123... | [Details] [Remove] |
| 2 | away | - | No | 92% | 18/20 | def456... | [Details] [Remove] |

Empty slots show:
"No accepted proposals for this time slot."

Total: N proposal(s) for this slot
```

**Columns:**
| Column | Type | Format | Notes |
|--------|------|--------|-------|
| # | number | 1, 2, 3... | Row number |
| State | string | Full name | predicted_state from proposal |
| Rooms | string | Comma-separated | From context_snapshot.rooms |
| Anyone Home | string | Yes/No | From context_snapshot.anyone_home |
| Confidence | number | Integer % | confidence x 100, rounded |
| Support | string | "count/total" | e.g., "22/25" |
| Proposal ID | string | Truncated (12 chars) | Resolved per §2.4, used for the Remove action; if resolution fails for an entry, show "—" and disable Remove for that row |
| Actions | buttons | "Details", "Remove" | **Details** reuses the panel's existing `_setDetail(kind, id)` raw-JSON inspection pattern (`heima-admin-panel.js:205`, rendering via `<pre>${JSON.stringify(...)}</pre>` at `heima-admin-panel.js:3023`) to show the full entry, including `learning_context` (deliberately not a table column — see §11.4's resolution) on demand. **Remove** calls the remove endpoint; disabled if `proposal_id` could not be resolved. |

**Style:**
- Table width: 100%
- Collapsible (only one slot detail open at a time)
- Header row: Bold, background `#F5F5F5`
- Remove button: Red text, `#F44336` background on hover

**Multiple proposals per slot:**
One (weekday, hour_bucket) can have multiple accepted proposals differentiated by:
- Different `rooms` context
- Different `anyone_home` value
- Different `learning_context`

All are shown in the detail table with their own Remove button.

---

## 4. Interaction Model

| Action | Behavior |
|--------|----------|
| Page load | Matrix renders with all 168 slots, showing proposal count per slot |
| Hover cell | Tooltip appears with slot summary (see §3.2) |
| Click cell | Expands/collapses detail table for that (weekday, hour_bucket) slot |
| Click Details button | Opens the existing raw-JSON detail view (`_setDetail`) for that entry, including `learning_context` |
| Click Remove button | Confirms via `window.confirm()` (§11.1), then calls `heima/observability/action` with `action: "review_proposal"`, `payload: {proposal_id, decision: "rejected"}` |
| Click outside table | Collapses detail view |
| Remove succeeds | Detail table refreshes, matrix updates, success toast |
| Remove fails | Error toast, detail table remains open |
| Responsive | Matrix scrolls horizontally on screens < 1200px wide |

---

## 5. Data Flow

### 5.1 Page Load
```
snapshot.learning.learning_modules
  -> Find module_id == "house_state_inference"
  -> Extract approved_model_entries
snapshot.proposals.raw.proposals
  -> Filter status === "accepted" AND identity_key starts with "house_state_learned_context:"
  -> Build a context_key -> proposal_id map
  -> Join onto approved_model_entries by context_key
  -> Group by (weekday, hour_bucket) from context_snapshot
  -> Build 7x24 matrix with proposal counts
  -> Render matrix + completion index
```

Both `snapshot.learning` and `snapshot.proposals` are already present on the single shared
observability snapshot object (`this._snapshot`) that every route's render method receives —
`_houseState(snapshot)` (route `"house_state"`) and `_learning(snapshot)` (route `"learning"`) are
both called with the exact same `snapshot` argument (`heima-admin-panel.js:719,724`), unlike
Topology/Actuators, which fetch their own dedicated snapshots. Extending `_houseState()` to also
read `snapshot.learning.learning_modules` and `snapshot.proposals.raw.proposals` requires no new
websocket command and no change to what data reaches the panel — only reading fields the method
doesn't currently look at.

### 5.2 Cell Click (Expand Detail)
```
On click cell (weekday, hour_bucket):
  -> Filter joined entries where context_snapshot.weekday == weekday AND context_snapshot.hour_bucket == hour_bucket
  -> Build detail table rows from matching entries (each already carrying its resolved proposal_id, or null)
  -> Render detail table
```

### 5.3 Remove Proposal
```
On click Remove for proposal_id:
  -> Call this._hass.callWS({
       type: "heima/observability/action",
       action: "review_proposal",
       payload: {
         proposal_id: proposal_id,
         decision: "rejected"
       }
     })
  -> On success: Reload snapshot, re-render matrix and detail
  -> On error: Show error toast
```

---

## 6. Backend Contract (No Changes Required)

**No backend changes are required** for the core visualization and removal functionality — the
`proposal_id` gap in §2.2 is resolved by joining two data sources that already reach the frontend
on the existing observability snapshot (§2.4), not by adding a field server-side.

### 6.1 Existing Data Sources

| Source | Snapshot path | Provides |
|--------|--------------|---------|
| HouseStateInferenceModule | `snapshot.learning.learning_modules` (module_id `"house_state_inference"`) | `approved_model_entries` with full context, no `proposal_id` |
| ProposalEngine | `snapshot.proposals.raw.proposals` | Every proposal (all statuses) with `id` (=proposal_id), `status`, `identity_key` — the join source for `proposal_id` |
| ApprovalStore | (backend-only, not directly exposed to the frontend) | Persistent approval decisions; consumed by the two sources above, not read by the panel itself |

`ProposalEngine.accepted_proposals()` (`proposal_engine.py:888`) is a Python-only method on
`coordinator.proposal_engine` — it is **not** callable from the frontend and is not itself part of
this feature's data path; it's mentioned here only because it's the backend equivalent of the
`status === "accepted"` filter the frontend applies to `snapshot.proposals.raw.proposals`.

### 6.2 Existing Endpoints

| Endpoint | Action | Purpose |
|---------|--------|---------|
| `heima/observability/action` | `review_proposal` | Accept/reject a proposal |
| `heima/observability/action` | `review_proposal_batch` | Batch accept/reject |

---

## 7. Frontend Implementation Notes

### 7.1 New Section in `_houseState()`

Add to `custom_components/heima/frontend/heima-admin-panel.js`:

```javascript
// In _houseState(snapshot):
const houseStateModule = (snapshot.learning?.learning_modules || [])
    .find(m => m.module_id === "house_state_inference");
const entries = houseStateModule?.approved_model_entries || [];
const isReady = houseStateModule?.ready || false;

// Resolve proposal_id per entry by joining against the accepted proposals list (§2.4/§5.1) —
// no new websocket call, snapshot.proposals is already loaded for this route.
const acceptedByContextKey = this._houseStateAcceptedProposalsByContextKey(snapshot);
const entriesWithProposalId = entries.map(entry => ({
    ...entry,
    proposal_id: acceptedByContextKey.get(entry.context_key) || null,
}));

// Group entries by (weekday, hour_bucket)
const slots = this._groupHouseStateEntriesBySlot(entriesWithProposalId);

// Render completion index + matrix
${isReady ? this._houseStateLearningMatrix(slots) :
    `<div class="card">House state learning data not ready.</div>`}
```

### 7.2 Helper Functions

| Function | Purpose |
|----------|---------|
| `_houseStateAcceptedProposalsByContextKey(snapshot)` | Builds a `Map<context_key, proposal_id>` from `snapshot.proposals.raw.proposals`, filtered to `status === "accepted"` and `identity_key` prefixed with `"house_state_learned_context:"` |
| `_groupHouseStateEntriesBySlot(entries)` | Groups approved_model_entries (with resolved `proposal_id`) by (weekday, hour_bucket) |
| `_houseStateLearningMatrix(slots)` | Renders 7x24 grid with proposal counts/colors |
| `_houseStateSlotTooltip(slot)` | Generates tooltip content for a slot |
| `_houseStateSlotDetail(slotKey, entries)` | Renders detail table for a specific slot, with Details/Remove buttons per row |
| `_removeHouseStateProposal(proposalId)` | Confirms via `window.confirm()` (§11.1), then calls WS endpoint (payload-nested, per §2.4) to reject a proposal |

No new helper is needed for the "Details" button — it reuses `_setDetail(kind, id)` and the panel's
existing generic detail-view renderer (`heima-admin-panel.js:205`, `:3023`) directly, the same way
every other object-inspection affordance in the panel does.

### 7.3 Slot Key Format

**Key:** `"weekday,hour_bucket"` (e.g., `"1,8"` = Monday, 8:00 AM)

Extracted from `context_snapshot`:
```javascript
const weekday = entry.context_snapshot.weekday;    // 0-6
const hourBucket = entry.context_snapshot.hour_bucket; // 0-23
const slotKey = `${weekday},${hourBucket}`;
```

---

## 8. Edge Cases & Validation

| Scenario | Behavior |
|----------|----------|
| No `learning_modules` in snapshot | Show: "Learning data unavailable" |
| `house_state_inference` module not found | Show: "House state learning not active" |
| Module not ready (`ready: false`) | Show: "Learning in progress..." + progress indicator |
| Empty `approved_model_entries` | Show: "No house state patterns accepted yet" |
| Slot with 0 proposals | Empty cell (gray background) |
| Slot with 1 proposal | Show state abbreviation |
| Slot with 2+ proposals | Show count with amber background |
| Entry's `proposal_id` could not be resolved (join miss) | Show "—" in Proposal ID column, disable that row's Remove button |
| Remove fails (404) | Show: "Proposal not found or already removed" |
| Remove fails (403) | Show: "Not authorized" |
| Remove fails (500) | Show: "Error removing proposal" |

---

## 9. Accessibility

| Requirement               | Implementation                          |
|---------------------------|-----------------------------------------|
| Color contrast            | All state colors pass WCAG AA (4.5:1)  |
| Keyboard navigation      | Tab through row headers, Enter to expand |
| Screen reader support     | ARIA labels for cells/day headers       |
| Reduced motion            | No animations on hover/expand            |

---

## 10. Acceptance Criteria

### Backend
- [x] `HouseStateInferenceModule.diagnostics()` returns `approved_model_entries` (already implemented, no `proposal_id` field — by design, see §2.2/§2.4)
- [x] `coordinator.async_review_proposal()` accepts proposals for rejection (already implemented)
- [x] `heima/observability/action` endpoint handles `review_proposal` (already implemented)

### Frontend
- [ ] Completion index shows `X/168 (Y%)` accurately
- [ ] 7x24 matrix renders with correct colors and counts
- [ ] Multiple proposals per slot shown with count indicator
- [ ] Hover tooltips show day, hour, state summary, proposal count
- [ ] Click cell expands detail table for that slot
- [ ] Detail table shows all proposals with full context
- [ ] `proposal_id` correctly resolved via the `snapshot.proposals.raw.proposals` join for every entry that has a matching accepted proposal
- [ ] Remove button present for each proposal in detail table; disabled with "—" shown when `proposal_id` could not be resolved
- [ ] Click Remove calls endpoint (payload-nested) and refreshes view
- [ ] Unlearned slots are gray/empty
- [ ] No console errors or warnings
- [ ] Responsive: matrix scrolls horizontally on mobile

### UX
- [ ] Visual hierarchy: completion index -> matrix -> details
- [ ] Colors are distinguishable (test with color-blind simulator)
- [ ] Tooltips appear within 200ms of hover
- [ ] Remove action confirms via `window.confirm()` before calling the endpoint (§3.4, resolved per §11.1 — same mechanism every other destructive action in this panel already uses)

---

## 11. Open Questions

None outstanding — all points raised during design discussion were resolved. See Resolved, below.

**Resolved:**

1. **Confirmation dialog.** Resolved by precedent, not by discussion: every existing destructive
   action in this panel (`delete_opening`, `delete_connection`, `delete_actuator`) confirms via
   `window.confirm(confirmMessage)` (`heima-admin-panel.js:118-119`, `:168-169`) — not a toast.
   Remove uses the same mechanism, message: "Remove accepted proposal for [state] at [day]
   [hour]:00?"
2. **Multi-select removal.** No for v1. `review_proposal_batch` already exists as a backend
   endpoint (§6.2), so batch removal is a low-cost future addition, not a redesign, if ever needed
   — not worth the added UI complexity for v1.
3. **Empty state filtering.** Not actually a separate design choice — it's already the direct
   consequence of the `status === "accepted"` filter baked into the `proposal_id` join (§2.4,
   §7.1). A slot with only rejected proposals has no accepted proposal to join against, so it's
   already empty by construction; no additional filtering logic needed.
4. **Context display.** Table columns stay as originally proposed (rooms, anyone_home, confidence,
   support) — `learning_context` is not a column. Instead, a **Details** button per row (§3.4, §4)
   reuses the panel's existing `_setDetail`/raw-JSON inspection pattern (`heima-admin-panel.js:205`,
   `:3023`, already used elsewhere for object inspection) to show the full entry, including
   `learning_context`, on demand — covers the "Debugging: identify anomalous learned states"
   purpose (§1) without a new UI mechanism or a cluttered table.

---

## 12. Dependencies

- **Backend**: None (uses existing HouseStateInferenceModule, ApprovalStore, and ProposalEngine data already exposed via the observability snapshot)
- **Frontend**: No new dependencies (pure HTML/CSS/JS)
- **Data**: Uses existing observability snapshot infrastructure — no new websocket command

---

## 13. Next Steps

1. **Spec approval**: Review and approve this specification
2. **Frontend implementation**: Implement matrix rendering and detail view in `_houseState()`
3. **Verify the `context_key` ⇄ `proposal_id` join rate against real data.**
   `approved_model_entries` (from `HouseStateInferenceModule`) and
   `snapshot.proposals.raw.proposals` (from `ProposalEngine`) both derive from the same
   `ApprovalStore` state but are computed independently by different modules (§2.4) — check how
   often, in practice, an entry fails to find a matching accepted proposal. A high miss rate would
   make the "disable Remove, show —" fallback (§8) the common case rather than a rare edge case,
   and would argue for revisiting with backend-side `proposal_id` enrichment (Option A, rejected
   in this draft for adding cross-layer plumbing `HouseStateInferenceModule` doesn't currently
   have — see the investigation behind §2.4) instead of the client-side join. Do this early in
   implementation, before building out the rest of the detail view on top of it.
4. **Add to navigation**: Ensure House State admin page is accessible from sidebar

---

## Appendix A: Context Key Format

From `approval_store.py:175-195`:

```python
def house_state_context_key(
    *,
    weekday: int,
    hour_bucket: int,
    rooms: list[str] | tuple[str, ...] | set[str],
    anyone_home: bool,
    predicted_state: str,
    learning_context: dict[str, Any] | None = None,
) -> str:
    normalized_rooms = _canonical_rooms(rooms)
    context = canonicalize_learning_context(learning_context or {})
    context_token = _context_hash(context)
    return (
        f"weekday:{int(weekday)}:"
        f"hour_bucket:{int(hour_bucket)}:"
        f"rooms:{','.join(normalized_rooms) if normalized_rooms else 'none'}:"
        f"anyone_home:{1 if anyone_home else 0}:"
        f"ctx:{context_token}:"
        f"state:{_token(predicted_state)}"
    )
```

The `context_snapshot` in `approved_model_entries` contains the parsed values:
```json
{
    "weekday": 1,
    "hour_bucket": 8,
    "rooms": ["living"],
    "anyone_home": true,
    "predicted_state": "working",
    "learning_context": {...}
}
```

---

## Appendix B: Proposal Lifecycle

Accepted house state proposals follow this lifecycle:

```
LearnedHouseStateCandidate (from HouseStateInferenceModule)
    ↓
ReactionProposal (identity_key = "house_state_learned_context:{context_key}")
    ↓
User accepts via config flow or auto-accept
    ↓
ApprovalStore records decision (context_key, proposal_type, decision="approved")
    ↓
HouseStateInferenceModule.sync_approval_state() adds to _approved_context_keys
    ↓
Module emits HouseStateSignal in infer() for matching contexts
    ↓
User clicks Remove in admin UI
    ↓
async_review_proposal(proposal_id, decision="rejected")
    ↓
ApprovalStore records decision="rejected"
    ↓
HouseStateInferenceModule.sync_approval_state() removes from _approved_context_keys
    ↓
Module stops emitting signals for this context
```

Proposal IDs are stable and can be used to reference specific accepted proposals for removal. The
admin UI resolves a given `approved_model_entries` entry's `proposal_id` by matching its
`context_key` against `identity_key` in `snapshot.proposals.raw.proposals` (see §2.4) — the two
data sources share the same `context_key`/`identity_key` values because both derive from the same
`ApprovalStore` state, but they are read independently (one from `HouseStateInferenceModule`'s own
diagnostics, one from `ProposalEngine`'s), so the join happens client-side rather than being a
single pre-joined structure.
