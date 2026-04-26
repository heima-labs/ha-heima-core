# Heima — Admin Control Center — Functional & UX Specification

Version: 0.1  
Status: Draft  
Scope: Admin dashboard for installer, advanced owner, operator  
Authoring context: desktop-first, standard HA sidebar visible, operator profile

---

## 1. Objective

Design the Heima admin control center for operators and advanced owners.

The dashboard must not behave like a raw diagnostics dump, an entity browser, or a debug console. It must instead act as a bounded, trustworthy control surface that answers four questions immediately:

1. Is the system healthy and running correctly?
2. Are there proposals that require review?
3. What reactions are configured and active?
4. Where do I go to configure or inspect something?

This dashboard is the primary entry point for configuration oversight and operational monitoring. It is not a real-time debug surface. Detailed investigation belongs in the debug/diagnostics surface kept separate.

---

## 2. Design principles

### 2.1 Product principles

- The interface must expose **Heima as a product**, not raw Home Assistant internals.
- The interface must privilege **operational clarity** over diagnostic completeness.
- The interface must privilege **bounded entry points** over full settings exposure.
- The interface must feel controlled, inspectable, and serious.
- It is acceptable for the admin surface to be denser than the non-admin surface.

### 2.2 UX principles

- No raw JSON dumps visible by default.
- No entity-browser feel.
- No "everything-in-one-page" approach — deep configuration stays in the options flow.
- Status indicators must communicate state, not raw values.
- The dashboard is a **navigation hub + operational status surface**, not a settings page.

### 2.3 Visual principles

- Same visual family as the non-admin dashboard.
- Moderate density: more information per card than non-admin, but still bounded.
- Neutral palette with sparse semantic accent colors (ok / warning / alert).
- Tables and structured lists are acceptable in admin context.
- Card hierarchy consistent with non-admin surface.

---

## 3. Target users

### 3.1 Primary users

- Installer configuring a new installation.
- Advanced owner overseeing system behavior.
- Operator performing routine maintenance or review.
- Investor evaluating product seriousness and configurability.

### 3.2 Excluded use cases

This dashboard is not optimized for:
- Real-time debug analysis.
- Raw event log inspection.
- Low-level entity state interrogation.
- Deep diagnostics (those belong in the debug surface).

---

## 4. Device and interaction context

### 4.1 Primary device

Desktop browser or tablet, landscape orientation.  
HA sidebar is visible (admin profile).

### 4.2 Interaction model

- Mouse/touch.
- Entry points to options flow (modal, full-page) via card actions.
- No destructive actions directly on this surface.

### 4.3 Performance expectations

- Status panels readable within 2 seconds.
- Entry points (options flow) load on tap without visible delay.

---

## 5. Information architecture

The admin control center contains exactly these sections, in this order:

1. System status
2. Proposals
3. Active reactions
4. Plugin families
5. Recent activity
6. Quick entry points

Explicitly excluded from this screen:
- Raw diagnostics JSON.
- Per-entity state lists.
- Full options flow settings.
- Historical graphs or trend charts.
- Debug event log.

---

## 6. Screen layout

### 6.1 Overall structure

- Row 1: System status (full width)
- Row 2: Proposals (left) + Active reactions (right) — 2 columns
- Row 3: Plugin families (left, 2/3 width) + Recent activity (right, 1/3 width)
- Row 4: Quick entry points (full width, 4 buttons)

### 6.2 Layout rationale

The 2-column split in Row 2 reflects the two main operational concerns: what needs attention now (proposals) and what is running (reactions). Plugin families are wider because they have more structured content.

### 6.3 Layout constraints

- Maximum columns: 2 (below Row 1).
- No dense 3–4 column tile matrices.
- Card spacing consistent with non-admin dashboard.

---

## 7. Section specification

## 7.1 System status

### 7.1.1 Purpose

Communicate the current operational state of Heima in one glance: is the engine running, is the house state stable, are there any health warnings?

### 7.1.2 Content model

- House state badge (current `heima_house_state` value)
- Engine health indicator: ok / warning / error
- Last engine run timestamp
- People at home: count from `heima_people_count`
- Active reactions count from `heima_reactions_active`
- Pending proposals count from `heima_reaction_proposals`

### 7.1.3 Example content

```
House state:     relax
Engine health:   ok     (last run: 18:42:01)
People at home:  0
Active reactions: 7
Pending proposals: 2
```

### 7.1.4 Functional requirements

- Must always show current house state.
- Must surface engine health prominently: any error state must be visually escalated.
- Must show pending proposals count; if > 0, escalate visually (attention indicator).
- Must not expose raw sensor key names.
- Must not include graphs.

### 7.1.5 Source entities

| Field | Source |
|---|---|
| House state | `sensor.heima_house_state` |
| Engine health | `sensor.heima_house_state` availability + `heima_house_state_reason` |
| Last run | `sensor.heima_home_view` → `last_update` attribute |
| People at home | `sensor.heima_people_count` |
| Active reactions count | `sensor.heima_reactions_active` (state value) |
| Pending proposals count | `sensor.heima_reaction_proposals` (state value) |

---

## 7.2 Proposals

### 7.2.1 Purpose

Surface the current proposal backlog so the operator can identify what requires review and navigate directly to the proposals flow.

### 7.2.2 Content model

- Count of pending proposals
- List of up to 3 pending proposal summaries, each showing:
  - Proposal type (family)
  - Brief description or reaction label
  - Age (how long ago it was created)
- "Review proposals" entry point → opens options flow → Proposals step

### 7.2.3 Example content

```
Pending proposals: 2

• lighting · Soggiorno relax · 2 days ago
• lighting · Camera buonanotte · 5 hours ago

[Review proposals →]
```

### 7.2.4 Functional requirements

- If pending count is 0: show "Nessuna proposta in attesa" in a calm, neutral state.
- If pending count > 0: escalate card visually (attention state).
- Show at most 3 proposals inline; if more, show count badge and entry point.
- Entry point must navigate directly to the Proposals step of the options flow.

### 7.2.5 Source entities

| Field | Source |
|---|---|
| Pending count | `sensor.heima_reaction_proposals` (state) |
| Proposal list | `sensor.heima_reaction_proposals` → `attributes` |

---

## 7.3 Active reactions

### 7.3.1 Purpose

Show what reactions are currently configured and active, broken down by provenance (learning vs admin-authored).

### 7.3.2 Content model

- Total active reactions count
- Breakdown by family (e.g. lighting: 4, presence: 2, scheduled_routine: 1)
- Muted reactions count (if any)
- "Manage reactions" entry point → opens options flow → Reactions step

### 7.3.3 Example content

```
Active reactions: 7  (muted: 1)

lighting           4
presence           2
scheduled_routine  1

[Manage reactions →]
```

### 7.3.4 Functional requirements

- Must show total count and per-family breakdown.
- Muted reactions must be noted but not visually alarming.
- If a family has 0 reactions, it may be omitted from the breakdown.
- Entry point navigates to the Reactions step of the options flow.

### 7.3.5 Source entities

| Field | Source |
|---|---|
| Total count | `sensor.heima_reactions_active` (state) |
| Per-reaction detail | `sensor.heima_reactions_active` → `attributes.reactions` |
| Muted count | `sensor.heima_reactions_active` → `attributes.muted_total` |

---

## 7.4 Plugin families

### 7.4.1 Purpose

Show which learning plugin families are enabled, and their current operational status (active learning, last event, no activity).

### 7.4.2 Content model

A structured table or list with one row per registered family:

| Family | Status | Last activity |
|---|---|---|
| lighting | enabled | 2 hours ago |
| presence | enabled | 1 day ago |
| scheduled_routine | always on | fired 18:30 |
| composite_room_assist | disabled | — |

### 7.4.3 Functional requirements

- Must show all registered families, enabled and disabled.
- `scheduled_routine` must be marked as "always on" (not toggled by the learning enabled_families setting).
- Disabled families must be visually distinct but not alarming.
- Last activity column may show "—" if no event is recorded.
- No entry point directly from this card in v1 (configuration is via options flow learning step).

### 7.4.4 Source entities

| Field | Source |
|---|---|
| Enabled families | `sensor.heima_event_store` → `attributes.by_type` or options config |
| Last activity | `sensor.heima_event_store` → `attributes.by_type` (event counts by family) |
| Family list | Static from registry (scheduled_routine, lighting, presence, composite_room_assist, ...) |

---

## 7.5 Recent activity

### 7.5.1 Purpose

Surface the last few system events of operational significance, so the operator has a sense of what Heima has been doing recently without reading a full event log.

### 7.5.2 Content model

A compact list of up to 4 recent events, each with:
- Event type (human label)
- Brief description
- Timestamp

Example event types to surface:
- Proposal created
- Proposal accepted / rejected
- Reaction fired (scheduled_routine)
- Binding orphaned (warning)
- Engine health change

### 7.5.3 Example content

```
Recent activity

• Reaction fired · Scheduled routine morning lights · 07:00
• Proposal created · Soggiorno relax · yesterday 19:42
• Proposal accepted · Camera buonanotte · 2 days ago
```

### 7.5.4 Functional requirements

- Maximum 4 items visible.
- Items ordered by recency, most recent first.
- Warning-class events (binding orphaned, health warning) must be visually escalated.
- Must not show raw event type keys (e.g. `reaction.fired` → "Reaction fired").
- No "open full log" entry point on this surface (debug log lives in debug surface).

### 7.5.5 Source entities

| Field | Source |
|---|---|
| Recent events | `sensor.heima_event_store` → `attributes` |
| Last event type | `sensor.heima_last_event` |
| Event stats | `sensor.heima_event_stats` |

---

## 7.6 Quick entry points

### 7.6.1 Purpose

Provide direct, bounded entry points into the options flow sub-sections that operators use most often.

### 7.6.2 Entry point set

Exactly four entry points:

| Label | Target |
|---|---|
| Proposals | Options flow → Proposals step |
| Reactions | Options flow → Reactions step |
| Scheduled routines | Options flow → Scheduled Routine step |
| Security simulation | Options flow → Security Presence Simulation step |

### 7.6.3 Functional requirements

- Four entry points in a single row on desktop.
- Each entry point is a button: icon + label.
- Tapping opens the corresponding options flow step.
- No descriptive text inside each button.
- If options flow cannot be opened from the dashboard directly, entry points link to the HA integrations settings page with Heima pre-selected.

### 7.6.4 Anti-requirements

Do not expose:
- Entry points to raw entity management.
- Entry points to HA automations.
- Entry points to debug diagnostics.
- More than four entry points on this surface.

---

## 8. Content sourcing model

The admin dashboard consumes existing canonical sensors directly. No new view entities are required.

### 8.1 Canonical sensors used

| Sensor | Usage |
|---|---|
| `sensor.heima_house_state` | System status — house state badge |
| `sensor.heima_house_state_reason` | System status — health indicator |
| `sensor.heima_people_count` | System status — people at home |
| `sensor.heima_reaction_proposals` | Proposals — count + list |
| `sensor.heima_reactions_active` | Active reactions — count + breakdown |
| `sensor.heima_event_store` | Plugin families + recent activity |
| `sensor.heima_last_event` | Recent activity — last event type |
| `sensor.heima_event_stats` | Recent activity — event summary |
| `sensor.heima_home_view` | System status — last engine run timestamp |

### 8.2 Sourcing rules

- The dashboard reads sensor state and attributes directly from HA.
- No semantic transformation is required before rendering.
- Attribute access (e.g. `heima_reactions_active.attributes.reactions`) is acceptable in this surface.
- The dashboard must not reconstruct meaning from raw HA device entities.

---

## 9. State and copy requirements

### 9.1 Copy style

- Short.
- Operator-appropriate: slightly more technical than the non-admin surface.
- Precise.
- No raw implementation identifiers (no entity IDs, no Python class names).
- Italian by default; same language as non-admin surface.

### 9.2 Terminology rules

Prefer:
- `lighting` over `LightingPlugin`
- `Proposta in attesa` over `pending_proposal`
- `Reaction fired` over `reaction.triggered`
- `always on` over `enabled=True hardcoded`

Avoid:
- Raw sensor keys as labels.
- Python dict keys as UI labels.
- Stack trace fragments.

### 9.3 Status indicators

| State | Color / style |
|---|---|
| ok / healthy | Neutral or soft green |
| attention (proposals pending, warning event) | Amber accent |
| error (engine failure, health error) | Red accent |
| disabled | Muted, visually subordinate |

---

## 10. Visual specification

### 10.1 Density

Moderate density. More information per card than the non-admin surface, but still bounded and readable.

### 10.2 Card style

Same card style as non-admin dashboard:
- Large radius.
- Soft contrast.
- Strong separation through spacing.

### 10.3 Typography

- Section titles clearly readable.
- Count values (proposals, reactions) visually prominent.
- Detail text (family list, activity list) visibly subordinate.
- Table content small but legible.

### 10.4 Color system

- Neutral base palette.
- Sparse semantic accents: ok (neutral/green), attention (amber), error (red), disabled (muted).
- No rainbow breakdowns.

### 10.5 Icons

- Consistent icon family.
- One icon per entry point button.
- No decorative icon usage in status panels.

---

## 11. Interaction specification

### 11.1 Interaction priorities

1. Read system health
2. Review and act on pending proposals
3. Inspect active reactions
4. Navigate into configuration via entry points
5. Review recent activity

### 11.2 Taps and actions

- System status: read-only, no taps.
- Proposals card: tap "Review proposals →" → opens proposals options flow step.
- Active reactions card: tap "Manage reactions →" → opens reactions options flow step.
- Plugin families: read-only in v1.
- Recent activity: read-only. No "open full log" on this surface.
- Quick entry points: tap → opens corresponding options flow step.

### 11.3 Navigation philosophy

The admin dashboard is a status overview and navigation hub. Deep configuration always happens in the options flow, never directly on the dashboard. This keeps the dashboard stable and the configuration surface authoritative.

---

## 12. Accessibility and usability requirements

- Sufficient contrast in normal ambient light.
- State must not rely on color alone (include text labels alongside color indicators).
- Tables must be scannable without zooming on desktop.
- Entry point buttons must have large touch targets on tablet.

---

## 13. Non-functional requirements

### 13.1 Maintainability

- Layout must be modular: sections independently evolvable.
- Entry points must not hardcode options flow step IDs that may change.

### 13.2 Reliability

- If a canonical sensor is unavailable, its section must degrade gracefully.
- A missing sensor must not collapse the entire dashboard layout.
- "Non disponibile" is an acceptable fallback for any field.

### 13.3 Performance

- Avoid excessive template complexity.
- Prefer direct sensor attribute access over computed template chains.

---

## 14. Explicit exclusions

This dashboard must not include:
- Raw JSON attribute dumps.
- Full event log.
- Per-entity HA device state.
- Automation editor entry points.
- Energy / history charts.
- Deep diagnostics panels.
- Settings for non-Heima integrations.

These belong in the debug/diagnostics surface or in HA's native admin UI.

---

## 15. Open architecture questions

### 15.1 Options flow entry points

HA does not currently support deep-linking to a specific step within an options flow from a dashboard card. The entry points in Section 7.6 may need to navigate to the integrations settings page with Heima pre-selected, rather than opening a specific step directly. This should be evaluated before implementation.

### 15.2 Recent activity source

`sensor.heima_event_store` currently exposes event counts by type, not a chronological event list. The recent activity section (7.5) requires a time-ordered list of recent events. This may require an additional attribute on `heima_event_store`, or a separate `sensor.heima_recent_events` sensor. Decision deferred to implementation phase.

### 15.3 Plugin families last activity

The per-family last activity timestamp is not currently exposed as a sensor attribute. This may require an extension to `heima_event_store` attributes or a new coordinator-level sensor. Decision deferred to implementation phase.

---

## 16. Acceptance criteria

The admin dashboard is successful if an operator can, within a few seconds:

- Confirm the engine is running and healthy.
- See how many proposals are pending and navigate to review them.
- See how many reactions are active and which families are represented.
- Navigate to configure reactions, scheduled routines, or security simulation.
- Understand recent system activity without opening a raw log.

The admin dashboard is not successful if:
- The operator must open raw diagnostics to understand basic system state.
- The dashboard looks like an entity browser.
- The entry points to configuration are absent or unclear.
- Debug data is surfaced as the primary content.

---

## 17. Future extensions (not part of v1 admin surface)

- Per-reaction drill-down view.
- Proposal review directly from dashboard (without entering options flow).
- Per-family learning progress timeline.
- System health history chart.
- Admin notification center (binding orphans, health errors, engine restarts).
- Multi-installation operator view.
