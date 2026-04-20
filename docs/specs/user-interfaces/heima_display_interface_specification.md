# Heima Display Interface Specification

## Non-Admin Tablet Experience (v1.0)

---

# 1. Purpose

This document defines the **standardized display architecture** for Heima’s non-admin user interface, designed to operate on a dedicated tablet device.

The goal is to create a **product-grade, reproducible interface layer**, not a one-off Home Assistant dashboard.

This specification ensures:

* deterministic behavior
* consistent UX across installations
* clear separation of responsibilities between system layers
* future portability (e.g., migration to custom frontend)

---

# 2. Design Principles

## 2.1 Appliance Model

The tablet must behave as a **single-purpose device**, not a general computing device.

* No visible OS navigation
* No access to underlying system UI
* No concept of “apps” for the user

## 2.2 Single Entry Point

The user interacts with **exactly one primary interface**:

* Heima Home Dashboard

No navigation complexity is exposed by default.

## 2.3 Semantic Interface

The UI must expose:

* **meaning (state)**
* **intent (actions)**

Never:

* raw entities
* technical telemetry

## 2.4 Deterministic Recovery

The system must **always return to the intended state**, regardless of:

* reboot
* crash
* user interaction errors

---

# 3. System Architecture

## 3.1 Layered Model

```
[Tablet Device]
    ↓
[Kiosk Runtime Layer]
    ↓
[Home Assistant Frontend]
    ↓
[Heima Dashboard UI]
    ↓
[Browser Control Layer]
    ↓
[Heima Core Logic]
```

---

## 3.2 Responsibilities by Layer

### Tablet Device

* hardware execution
* OS lifecycle (boot, sleep, wake)

---

### Kiosk Runtime Layer

**Primary component: Fully Kiosk Browser**

Responsibilities:

* auto-start on boot
* fullscreen enforcement
* UI lockdown (no exit paths)
* wake/sleep behavior
* recovery after failure

---

### Home Assistant Frontend

* rendering engine
* websocket connection
* state updates

---

### Heima Dashboard UI

* visual representation of system state
* interaction surface for user intents

---

### Browser Control Layer

**Primary component: browser_mod**

Responsibilities:

* popup orchestration
* controlled navigation
* browser-specific behavior
* UI flow management

---

### Heima Core Logic

* house state engine
* domain orchestration
* semantic sensors (view model)
* scripts (intent execution)

---

# 4. Technology Stack (Approved)

## 4.1 Mandatory Components

| Layer             | Component                |
| ----------------- | ------------------------ |
| Kiosk Runtime     | Fully Kiosk Browser      |
| UI Rendering      | Home Assistant Dashboard |
| UI Control        | browser_mod              |
| UI Simplification | Kiosk Mode               |

---

## 4.2 Optional Components

| Component     | Use Case                                     |
| ------------- | -------------------------------------------- |
| Companion App | Alternative launcher (non-dedicated tablets) |
| Screensaver   | Idle aesthetic layer                         |

---

# 5. Role-Based Capability Matrix

## 5.1 Boot and Recovery

| Capability         | Owner       |
| ------------------ | ----------- |
| Start on boot      | Fully Kiosk |
| Reload dashboard   | Fully Kiosk |
| Recover from crash | Fully Kiosk |

---

## 5.2 UI Lockdown

| Capability             | Owner       |
| ---------------------- | ----------- |
| Hide navigation UI     | Kiosk Mode  |
| Prevent app switching  | Fully Kiosk |
| Block system UI access | Fully Kiosk |

---

## 5.3 Navigation Control

| Capability                       | Owner       |
| -------------------------------- | ----------- |
| Force return to home             | browser_mod |
| Prevent deep navigation          | UI design   |
| Replace navigation with overlays | browser_mod |

---

## 5.4 Interaction Model

| Capability              | Owner               |
| ----------------------- | ------------------- |
| Primary actions         | Dashboard           |
| Contextual interactions | browser_mod (popup) |
| State feedback          | Heima sensors       |

---

## 5.5 Device Behavior

| Capability         | Owner       |
| ------------------ | ----------- |
| Screen on/off      | Fully Kiosk |
| Motion detection   | Fully Kiosk |
| Brightness control | Fully Kiosk |

---

# 6. UI Interaction Model

## 6.1 Navigation Paradigm

The interface is **single-screen dominant**.

### Rules:

* No multi-page navigation for primary flows
* No visible routing complexity
* All deep interactions use **overlay/popup patterns**

---

## 6.2 Popup Strategy (Mandatory)

All secondary interactions must use popups:

Examples:

* room details
* security detail
* climate detail

### Implementation

Handled via `browser_mod`.

---

## 6.3 Return-to-Home Behavior

The system must automatically:

* return to the main dashboard after inactivity
* close any popup state

Handled via:

* browser_mod automation
* optional HA timers

---

# 7. Dashboard Structure (Reference)

## 7.1 Fixed Layout Sections

1. Hero (house state)
2. Quick Actions (4 intents)
3. Rooms (2x2 grid)
4. Insights (left column)
5. Security (right column)
6. Climate (left bottom)

---

## 7.2 Navigation Constraints

* No sidebar for non-admin
* No header controls
* No entity lists

---

# 8. Device Configuration Standard

## 8.1 Fully Kiosk Required Settings

* Auto Start on Boot → ENABLED
* Start URL → Heima Dashboard
* Fullscreen → ENABLED
* Kiosk Mode → ENABLED
* Hide System UI → ENABLED
* Screen On Control → ENABLED

---

## 8.2 Network Requirements

* Persistent local network access
* Stable HA endpoint (local preferred)
* No dependency on external cloud

---

# 9. Failure Handling

## 9.1 Supported Recovery Scenarios

| Scenario         | Behavior                      |
| ---------------- | ----------------------------- |
| Device reboot    | Auto return to dashboard      |
| Browser crash    | Auto reload                   |
| Navigation drift | Forced return via browser_mod |
| UI inconsistency | Stateless redraw from HA      |

---

## 9.2 Non-Goals

The system does not guarantee:

* resilience to OS-level failures
* protection from physical tampering
* absolute kiosk security under rooted devices

---

# 10. Extensibility Strategy

## 10.1 Future Migration Path

This architecture allows migration to:

* custom HA panel
* external frontend app

Because:

* UI consumes semantic sensors
* logic is not embedded in UI
* interaction model is abstracted

---

## 10.2 Productization Constraints

To remain a product (not custom setup):

* no hardcoded entity IDs in UI
* configuration-driven mapping
* standardized naming conventions
* reusable component patterns

---

# 11. Key Architectural Decisions (Summary)

1. Use **Home Assistant dashboard** as UI layer
2. Use **Fully Kiosk** as device runtime
3. Use **browser_mod** for interaction orchestration
4. Use **Kiosk Mode** for UI simplification
5. Enforce **single-screen interaction model**
6. Centralize all logic in **Heima core (not UI)**

---

# 12. Final Statement

This specification defines Heima’s non-admin interface as a:

> **controlled, deterministic, appliance-like system interface**

—not a configurable dashboard.

The separation between:

* device runtime
* UI rendering
* browser orchestration
* system intelligence

is intentional and required to maintain:

* reliability
* clarity
* scalability
* product-level consistency

---

END OF SPEC
