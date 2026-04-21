# Heima — Dashboard non-admin (Home) — Functional & UX Specification

Version: 0.1  
Status: Draft for architecture review  
Scope: Main home dashboard for non-admin users  
Authoring context: tablet-first, landscape, Apple-like minimal interface

---

## 1. Objective

Design the primary Heima dashboard for non-admin household users.

The dashboard must not behave like a technical control panel, an entity browser, or an admin console. It must instead act as a calm, legible, high-trust interface that answers four questions immediately:

1. What is the current situation in the house?
2. What can I do right now?
3. What is the status of the main rooms?
4. Why is the house behaving this way?

This dashboard is the main daily entry point for normal users. It is not intended for configuration, diagnostics, maintenance, or automation authoring.

---

## 2. Design principles

### 2.1 Product principles

- The interface must expose **Heima**, not raw Home Assistant internals.
- The interface must privilege **meaning** over telemetry.
- The interface must privilege **clarity** over density.
- The interface must privilege **safe actions** over complete control.
- The interface must feel calm, premium, domestic, and trustworthy.

### 2.2 UX principles

- No admin vocabulary.
- No raw entity identifiers.
- No YAML-oriented or automation-oriented mental model.
- No walls of badges, chips, or sensors.
- No high-frequency animated noise unless required for an alert.
- No “everything dashboard” approach.

### 2.3 Visual principles

- Apple-like minimalism.
- Large cards, generous spacing, high legibility.
- Neutral palette, sparse semantic accents.
- Rounded surfaces, soft hierarchy, limited ornament.
- Touch-friendly targets.
- Clear typography hierarchy.

---

## 3. Target users

### 3.1 Primary users

Household members who:
- are not Home Assistant administrators;
- do not know the internal automation model;
- need immediate comprehension and safe everyday controls;
- may interact via wall tablet or shared tablet.

### 3.2 Excluded users / excluded use cases

This dashboard is not optimized for:
- advanced debugging;
- automation editing;
- service calls;
- device-level administration;
- entity inspection;
- historical analysis;
- energy/observability deep dives.

Those functions must live elsewhere.

---

## 4. Device and interaction context

### 4.1 Primary device

Tablet, landscape orientation, approximately 8–11 inches.

### 4.2 Interaction model

- Primarily touch.
- Occasional glanceable use from medium distance.
- Shared household use.
- Must remain usable without training.

### 4.3 Performance expectations

- Fast initial render.
- Stable layout, no jumpy reflow.
- No dependence on complex page transitions for core comprehension.
- Core status readable within 2 seconds.

---

## 5. Information architecture

The main home dashboard contains exactly these sections, in this order:

1. Hero / house state
2. Quick actions
3. Main rooms
4. Heima insights
5. Security
6. Climate & comfort

Explicitly excluded from this screen:
- media / entertainment controls;
- admin controls;
- diagnostic panels;
- detailed energy;
- historical graphs;
- raw alert/event logs;
- full room/device inventory.

Media and entertainment belong in a dedicated dashboard.

---

## 6. Screen layout

### 6.1 Overall structure

The screen is composed as follows:

- Row 1: Hero section (full width)
- Row 2: Quick actions (full width)
- Row 3: Main rooms grid (2 columns × 2 rows)
- Row 4: Heima insights (left) + Security (right)
- Row 5: Climate & comfort (left) + intentional empty breathing space (right)

### 6.2 Layout rationale

The right-side empty space in the last row is intentional.
It prevents visual crowding, preserves calmness, and avoids the common anti-pattern of filling every available slot with lower-value content.

### 6.3 Layout constraints

- Maximum visual density: low.
- Maximum columns in content area below hero/actions: 2.
- No dense 3–4 column tile matrices.
- Card spacing must be consistent.
- Vertical rhythm must be obvious and stable.

---

## 7. Section specification

## 7.1 Hero / House state

### 7.1.1 Purpose

Communicate the current global condition of the home in one glance.

This is the semantic anchor of the entire dashboard and the clearest expression of Heima’s value.

### 7.1.2 Content model

The hero contains:
- small label: product or home label (e.g. “Heima”)
- dominant title: current house state
- secondary line: compressed natural-language explanation
- 3 to 4 compact pills containing global summary data

### 7.1.3 Example content

- Label: `Heima`
- Title: `Casa in relax`
- Secondary line: `Luci soft nel soggiorno, ambiente stabile`
- Pills:
  - `21.2 °C`
  - `Sicurezza ok`
  - `Garage occupato`
  - `Pioggia debole`

### 7.1.4 Functional requirements

- Must always show the current global house state.
- Must always prefer human language over implementation detail.
- Must include security status in discursive, synthetic form as a pill or equivalent summary.
- Must not show more than one secondary sentence.
- Must not include graphs.
- Must not include more than 4 pills.

### 7.1.5 Semantic requirements

The hero must answer:
- what mode the house is in;
- what the system is broadly doing;
- whether there is any global issue worth immediate attention.

### 7.1.6 Anti-requirements

The hero must not become:
- a notification stream;
- a statistics area;
- a debug area;
- a safety panel duplicate.

---

## 7.2 Quick actions

### 7.2.1 Purpose

Expose the few high-value, low-risk actions that normal users perform frequently.

### 7.2.2 Action set

The dashboard exposes exactly these quick actions:
- Relax
- Buongiorno
- Buonanotte
- Ospiti

### 7.2.3 Functional requirements

- Actions must map to high-level Heima intentions, not raw device commands.
- Actions should be implemented as orchestrated scenes, scripts, workflows, or domain-level intents.
- Actions should be idempotent where possible.
- Active/engaged state may be visually represented, but subtly.

### 7.2.4 Layout requirements

- Four actions in a single row on landscape tablet.
- Large touch targets.
- Icon + label.
- No descriptive paragraphs inside each action.

### 7.2.5 Anti-requirements

Do not include:
- rare actions;
- admin overrides;
- raw service operations;
- dangerous or ambiguous controls;
- fine-grained room/device commands.

---

## 7.3 Main rooms

### 7.3.1 Purpose

Provide a room-based reading of the home that feels natural to household users.

### 7.3.2 Room set

Initial room set:
- Soggiorno
- Camera
- Cucina
- Garage

Optional future substitution:
- Ingresso may replace one room if it proves more useful.

### 7.3.3 Card model

Each room card contains:
- room name;
- up to 2 lines of synthesized room status;
- up to 2 actions.

### 7.3.4 Example room cards

#### Soggiorno
- `Luci soft attive`
- `TV accesa`
- actions: light, scene/media shortcut

#### Camera
- `Luci spente`
- `Ambiente tranquillo`
- actions: light, bedtime shortcut

#### Cucina
- `Nessuna attività rilevante`
- `Tutto regolare`
- actions: light, main appliance shortcut if justified

#### Garage
- `Auto presente`
- `Porta chiusa`
- actions: light, access/camera shortcut

### 7.3.5 Functional requirements

- Room content must be synthesized upstream where possible.
- The UI must not perform visible complexity assembly from raw entities if that can be avoided.
- Each room card must remain concise and readable.
- Status language must be domestic, not technical.

### 7.3.6 Anti-requirements

No room card may include:
- raw binary_sensor state labels;
- more than 2 visible actions;
- 3+ lines of telemetry;
- long entity lists;
- graphs.

---

## 7.4 Heima insights

### 7.4.1 Purpose

Expose the reasoning and current behavior of the Heima system in a calm, human-readable way.

This section is where the system demonstrates intelligence without looking like logs.

### 7.4.2 Presentation mode

Selected presentation mode: **Option A** — compact elegant list.

### 7.4.3 Content model

A compact list of up to 3 short insights.

Examples:
- `Nessuno in casa da 1h 12m`
- `Preheat non necessario`
- `Meteo fallback attivo`
- `Garage occupato dalle 18:42`
- `Stato Working per presenza e fascia oraria`

### 7.4.4 Functional requirements

- Maximum visible insights: 3.
- Each insight must be short.
- Each insight must express meaning, not internals.
- Insights should be prioritized by relevance.
- Insights should feel explanatory, not alarming, unless there is an actual alert.

### 7.4.5 Anti-requirements

Do not include:
- stack traces;
- raw rule names;
- implementation identifiers;
- too many simultaneous insights;
- verbose explanations.

---

## 7.5 Security

### 7.5.1 Purpose

Provide a structured, trustworthy summary of security and access-related status.

### 7.5.2 Relationship with Hero

Security status appears in two levels:
- Hero: synthetic discursive summary (e.g. `Sicurezza ok`)
- Security card: structured detail

This is intentional and not considered duplication.

### 7.5.3 Content model

The security card contains:
- title;
- one summary line;
- 2 to 4 structured sub-lines for important access/safety states.

Example normal state:
- `Tutto regolare`
- `Ingresso chiuso`
- `Garage chiuso`
- `Allarme disinserito`

Example exception state:
- `Attenzione`
- `Finestra cucina aperta`
- `Allarme disinserito`

### 7.5.4 Functional requirements

- Must summarize alarm status in plain language.
- Must summarize important entry points.
- Must visually escalate exceptions in a calm but clear way.
- Must avoid “industrial alarm panel” aesthetics.

### 7.5.5 Anti-requirements

Do not show:
- every contact sensor individually;
- technical state values;
- oversized red alarm styling when no real alarm condition exists.

---

## 7.6 Climate & comfort

### 7.6.1 Purpose

Represent whether the house feels comfortable and what the climate system is doing, without turning the dashboard into a thermostat console.

### 7.6.2 Presentation mode

Selected mode: **A — minimal**.

### 7.6.3 Content model

The climate card contains:
- title;
- dominant current indoor temperature;
- one comfort line;
- one system behavior line.

Example:
- `21.0 °C`
- `Comfort buono`
- `Riscaldamento in mantenimento`

### 7.6.4 Functional requirements

- No chart on this screen.
- No historical trend on this screen.
- Must communicate comfort, not just HVAC state.
- Must prefer a single dominant indoor temperature reference.

### 7.6.5 Anti-requirements

Do not include:
- scheduler internals;
- raw hvac_action noise;
- multiple mini-metrics that compete visually;
- engineering-style detail.

---

## 8. Content sourcing model

The dashboard should consume **already-curated semantic entities** whenever possible, rather than building meaning directly in the presentation layer.

Preferred source hierarchy:

1. Heima semantic sensors / derived entities
2. Heima scripts / intents / domain abstractions
3. Selected Home Assistant entities only where semantic wrapping is unnecessary

Examples of preferred semantic inputs:
- global house state
- house-state explanation summary
- room summaries
- security summary
- climate summary
- occupancy summary

The dashboard should not become the place where core house logic is encoded.

---

## 9. State and copy requirements

### 9.1 Copy style

- Short.
- Natural.
- Domestic.
- Reassuring.
- Precise.
- Never cute.
- Never nerdy.

### 9.2 Terminology rules

Prefer:
- `Sicurezza ok`
- `Casa in relax`
- `Garage occupato`
- `Comfort buono`
- `Tutto regolare`

Avoid:
- `binary_sensor on`
- `armed_away`
- `hvac_action idle`
- `entity unavailable`
- raw English state tokens unless absolutely necessary

### 9.3 Alert copy

Alert copy must be:
- short;
- directly actionable;
- not theatrical.

Examples:
- `Porta ingresso aperta`
- `Finestra cucina aperta`
- `Clima non disponibile`

---

## 10. Visual specification

### 10.1 Density

Low density.

### 10.2 Card style

- Large radius.
- Soft contrast.
- Premium but restrained.
- Strong separation through spacing, not heavy borders.

### 10.3 Typography

- Hero title clearly dominant.
- Secondary text visibly subordinate.
- Card titles readable at distance.
- Body copy concise and evenly spaced.

### 10.4 Color system

- Neutral base palette.
- Sparse semantic accent colors only.
- Accent colors reserved for active states and warnings.
- Avoid rainbow dashboards.

### 10.5 Icons

- Consistent icon family.
- Functional, not decorative.
- Used sparingly.

---

## 11. Interaction specification

### 11.1 Interaction priorities

1. Read global state
2. Trigger quick actions
3. Inspect main rooms
4. Understand why the house behaves this way
5. Verify security and comfort

### 11.2 Taps and drills

- Quick actions: immediate high-level action.
- Room cards: optional tap to dedicated room view or light secondary action.
- Security card: optional tap to dedicated security detail view.
- Climate card: optional tap to dedicated climate view.

### 11.3 Navigation philosophy

The home dashboard must be self-sufficient for daily use.
Users should not need to leave this screen for common daily interactions.

---

## 12. Accessibility and usability requirements

- Readable at glance from a moderate distance.
- Sufficient contrast in normal ambient light.
- Large touch targets.
- State should not rely on color alone.
- Critical states must be understandable without animation.

---

## 13. Non-functional requirements

### 13.1 Maintainability

- Layout should be modular.
- Cards/sections should be independently evolvable.
- Semantic logic should be externalized from the view.

### 13.2 Reliability

- Degraded data must fail gracefully.
- If a secondary source is unavailable, the dashboard should remain calm and legible.
- Missing optional data must not collapse the layout.

### 13.3 Performance

- Avoid excessive card nesting.
- Avoid excessive template complexity in the final rendering layer.
- Prefer precomputed semantic sensors where possible.

---

## 14. Explicit exclusions

This dashboard must not include:
- full entertainment controls;
- full weather page;
- full energy page;
- long historical charts;
- notification archive;
- automation toggles intended for admins;
- settings;
- diagnostics;
- logs;
- system health.

These belong in dedicated secondary dashboards.

---

## 15. Open architecture questions for the next phase

The UI specification above is intentionally technology-agnostic.
The next architecture phase must evaluate at least these implementation options:

1. Native Home Assistant dashboard
2. Home Assistant dashboard with custom cards/theme layer
3. Home Assistant custom panel/frontend app inside HA
4. External web app consuming HA APIs
5. Hybrid approach (HA for data/auth, external frontend for premium UI)

The architecture review must compare:
- UX quality ceiling
- implementation complexity
- maintainability
- latency and reliability
- kiosk/tablet behavior
- offline/local-first fit
- auth/session complexity
- compatibility with Heima semantic model

---

## 16. Acceptance criteria

The dashboard is successful if a non-admin user can, within a few seconds:

- understand the house’s current mode;
- see whether everything is broadly okay;
- trigger one of the four main house actions;
- understand the status of the main rooms;
- understand at least in simple terms why the system is behaving as it is.

The dashboard is not successful if users perceive it as:
- a technical panel;
- a cluttered smart-home board;
- an admin interface;
- a collection of unrelated widgets.

---

## 17. Future extensions (not part of v1 home screen)

Potential future dashboards:
- Entertainment
- Security detail
- Climate detail
- Per-room views
- Vacation / away mode detail
- Admin / diagnostics

These are explicitly out of scope for this specification version.
