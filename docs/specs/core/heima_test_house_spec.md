# Heima Test House Subproject Spec

**Status:** Draft — planned internal subproject
**Last Updated:** 2026-04-07

## Purpose

Define a future internal Heima subproject that provides a deterministic fake
home environment for:

- live validation
- product debugging
- end-to-end feature development
- onboarding and reproducible demos

This subproject is not a generic smart-home simulator. It is an **official
Heima test house** whose goal is to give the main repository a stable, repeatable
system-level environment.

---

## 1. Problem Statement

The repository already contains a strong but scattered live-test lab:

- Docker stack under `docs/examples/ha_test_instance/`
- HA config and fake house entities
- fixture restore and scenario scripts under `scripts/live_tests/`
- dashboard examples and test-specific surfaces

This material is already useful, but today it is still framed as:

- examples
- ad hoc live-test support
- loosely grouped operational tooling

That framing is becoming too weak for the current level of usage.

The lab is now important for:

- validating families like `security_presence_simulation`
- reproducing runtime and learning behavior
- testing dashboards and admin flows
- maintaining deterministic end-to-end development workflows

So the repo should treat it as a real internal subproject rather than as a
collection of examples.

---

## 2. Target Outcome

Heima should eventually contain a dedicated subproject:

- `lab/heima_test_house/`

This subproject should provide:

- a bootable Home Assistant lab stack
- a canonical fake home model
- deterministic fixture reset and scenario seeding
- validation entrypoints for live smoke and feature tests
- dashboard and operator surfaces for reading and controlling the fake house

The subproject should be maintained as **product support infrastructure** for
Heima, not as a public end-user deliverable.

---

## 3. Scope

### In Scope

- deterministic fake entities for a representative home
- Docker-based HA test stack
- fake lighting, heating, security, presence, MQTT, and calendar surfaces
- fixture generation and restore workflow
- scenario scripts for repeatable learning/runtime setup
- dashboards and panels used to read the lab as a product
- live smoke tests and feature validation entrypoints
- documentation for development and debugging use

### Out of Scope

- universal smart-home simulation
- physical accuracy of a real house
- replacing unit/integration tests
- supporting many different fake homes in parallel
- public distribution as a standalone independent product

---

## 4. Why This Should Exist

### Benefits

- reduces the cost of testing new runtime and learning features end-to-end
- gives Heima a canonical fake house for debugging and demos
- makes live tests more deterministic and explainable
- lets new features be validated before reaching a real home
- supports onboarding without requiring a production HA instance
- provides a clean place for dashboards, scenarios, and fixtures to live

### Tradeoffs

- introduces an internal subproject that must be maintained
- increases coupling to Home Assistant version behavior
- can create false confidence if the fake house is treated as “real enough”
- requires discipline around fixture versioning and reset semantics
- can grow into a second codebase if scope is not controlled

---

## 5. Difficulty Assessment

### Low / Medium Difficulty

If the goal is only:

- formalize the current lab
- move it to a stable location
- give it structure and ownership
- provide canonical startup/reset commands

### Medium Difficulty

If the goal is:

- make it a stable internal subproject
- define official scenarios
- keep fixtures deterministic across development
- version dashboards and operational surfaces cleanly

### Medium / High Difficulty

If the goal is:

- build a highly realistic fake house
- model many seasonal and behavioral variations
- maintain many home topologies or personas

This specification targets the **medium-difficulty** version:

- one official test house
- deterministic and useful
- not universal

---

## 6. Recommended Location and Naming

Recommended location:

- `lab/heima_test_house/`

Recommended framing:

- official Heima test house
- internal live-validation environment

Rejected framings:

- “just an example docker setup”
- “full home simulator”
- “multiple alternative fake homes”

---

## 7. Subproject Structure

The subproject should be split into four clear areas.

### 7.1 Infra

Path:

- `lab/heima_test_house/infra/`

Responsibility:

- container orchestration
- HA base config
- MQTT broker config
- bootstrap entrypoints
- version pinning and runtime compatibility

Expected contents:

- `docker-compose.yaml`
- HA config bootstrap files
- broker config
- startup helpers

### 7.2 House Model

Path:

- `lab/heima_test_house/house/`

Responsibility:

- canonical fake home definition

Expected contents:

- helper-backed fake entities
- fake lights
- fake climate
- fake alarm
- template and MQTT entities
- utility scripts and scene generators
- calendar fixtures
- baseline storage or baseline generation inputs

The house model should represent:

- a single canonical home
- enough variety for cross-domain testing
- bounded complexity

### 7.3 Validation

Path:

- `lab/heima_test_house/validation/`

Responsibility:

- deterministic reset
- smoke checks
- scenario application
- feature validation runners

Expected contents:

- restore/reset scripts
- fixture generators
- live smoke scripts
- per-feature scenario setup helpers

### 7.4 Surfaces

Path:

- `lab/heima_test_house/surfaces/`

Responsibility:

- operator-facing views of the fake house and Heima state

Expected contents:

- production-like dashboard example
- debug dashboard example
- family-specific panels where useful
- reading guides for diagnostics

---

## 8. Current Material To Migrate

The current implementation base already exists in scattered form.

Primary source material:

- `docs/examples/ha_test_instance/`
- `scripts/live_tests/006_restore_learning_fixtures.sh`
- `scripts/live_tests/044_security_presence_simulation_vacation.py`
- `scripts/live_tests/045_security_presence_simulation_learned_flow.py`
- `docs/examples/heima_dashboard_debug.yaml`
- `docs/examples/heima_dashboard_production.yaml`
- `docs/examples/heima_security_presence_panel.yaml`

Migration does not need to happen all at once.

During migration, compatibility shims or wrapper scripts are acceptable.

---

## 9. Migration Strategy

### Phase 1 — Formalization

Goal:

- create the subproject skeleton without changing behavior

Work:

- create `lab/heima_test_house/`
- move or copy the current HA test instance into the new structure
- add a canonical README
- define stable entrypoint commands

Success criteria:

- current lab can still boot
- reset flow still works
- no feature behavior changes required

### Phase 2 — Stabilization

Goal:

- make the subproject reliable and easy to use

Work:

- separate infra from house model from validation
- define canonical reset/start/stop commands
- make fixture restore deterministic and documented
- remove accidental repo coupling where possible

Success criteria:

- new contributors can boot the lab with one documented path
- live tests rely on stable subproject entrypoints

### Phase 3 — Productization

Goal:

- treat the test house as official internal product infrastructure

Work:

- define canonical scenarios
- define dashboard ownership and reading guidance
- define which new families/features require test-house coverage
- clean up legacy paths and transitional wrappers

Success criteria:

- the lab is the default place to validate major new features before real-home testing

---

## 10. Ownership and Governance

The subproject should own:

- deterministic live validation for Heima
- canonical fake house model
- lab surfaces and scenarios
- reset/bootstrap workflows

The subproject should not own:

- all testing in the repository
- full simulation of real-home complexity
- generic HA examples unrelated to the test house

Rules:

- one official fake house, not many
- changes to the house model should stay additive and purposeful
- new complexity must justify test value
- fixture reset must remain deterministic
- dashboards must optimize for operability, not visual novelty

---

## 11. Commands and Developer UX

The final subproject should expose a small set of canonical commands.

Recommended command surface:

- `up`
- `down`
- `reset`
- `run_smoke`
- `run_feature <feature>`

Exact implementation may be:

- shell scripts
- Make targets
- task runner targets

But the user-facing contract should stay small and stable.

---

## 12. Interaction With The Main Heima Repo

The subproject should stay in the main repository because it depends on:

- current `custom_components/heima`
- internal live-test scripts
- feature-specific diagnostics and dashboards

This is a strong argument against splitting it into a separate repository too early.

A separate repo would increase:

- synchronization cost
- fixture drift
- integration friction

So the default plan should be:

- same repo
- separate subproject boundary

---

## 13. Risks

### Risk: Scope Explosion

Mitigation:

- keep one canonical fake house
- reject “nice to have” realism that does not improve testing value

### Risk: Fixture Drift

Mitigation:

- version baseline fixtures
- keep deterministic restore
- document ownership of `.storage` and generated artifacts

### Risk: False Confidence

Mitigation:

- explicitly treat the test house as a bounded validation environment
- continue using unit/integration tests and real-home checks when needed

### Risk: HA Version Fragility

Mitigation:

- keep bootstrap and restore scripts explicit
- pin assumptions in infra docs
- prefer deterministic fake integrations over brittle external dependencies

---

## 14. Acceptance Criteria For The Subproject

The subproject is successful when:

- a developer can boot the test house from a single documented entrypoint
- the fake house exposes the canonical Heima validation signals needed by current domains
- deterministic restore reliably returns the house to a known baseline
- live feature tests can target the test house without ad hoc setup
- the dashboards and surfaces are useful for product debugging
- the subproject remains bounded and does not try to model every real-home detail

---

## 15. Recommended Next Step

When development resumes, the first implementation step should be:

- create the directory skeleton for `lab/heima_test_house`
- migrate the current HA test instance material into it with minimal behavior change
- keep temporary compatibility wrappers for current script paths

That gives the project a real boundary first, before deeper cleanup or expansion.
