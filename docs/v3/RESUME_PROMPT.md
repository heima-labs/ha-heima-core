# Prompt to resume V3 implementation

Use this prompt when starting a new chat in the V3 implementation worktree. It is also a checklist after context compaction; the repository files, not the chat summary, carry the durable state.

> We are implementing Heima V3 in the `ha-heima-component-v3-implementation` worktree on `feat/v3-implementation`. First confirm this is the current working directory; if another tree is open, navigate to this worktree before editing. Read root `AGENTS.md`, `docs/v3/WORKING_CONTEXT.md`, `docs/v3/CODE_RULES.md`, and `docs/v3/DEVELOPMENT_POLICY.md`. Check `git status`, branch and recent commits; reconcile any difference from the context file, including uncommitted instruction changes. For the current task, check Git status and HEAD in the adjacent `ha-heima-component-v3-planning` worktree, then read the authoritative layer specification and its contract dependencies there (Layer 0–6 and Layer 8 are currently authoritative), starting with its `AGENTS.md`, contract registry and spec workflow. That worktree's committed specs are currently newer than this code checkout's copies. Identify approved requirements, current issue status, and implementation decisions separately. Continue the recorded next action, or follow my newer instruction. Work in a bounded slice, use the approved five-method testing rule, and update `WORKING_CONTEXT.md` before stopping with exact files, evidence, risks and next step. Do not infer implementation or test completion from a specification's DONE status. Git and deployment sections are proposals pending developer review; do not treat them as approved. Do not deploy or merge without the required authorization.

If the user gives a new objective, that instruction takes precedence over the recorded next action. If the context file is stale, repair it from Git and the actual files. Never let this prompt override current user instructions or the authoritative V3 layer contracts.

## Layer 0/1 synchronization checkpoint

At planning `c8a68a8`, the Claude handoff for CA4-71/72/73/74/75/78/79/80 was
checked against the owning specs. Read the eight-item mapping in WORKING_CONTEXT
before continuing the fact-model discussion. HouseFact still has exactly five fields.
Notification event values contain notification_key, severity, context_version and
closed context, never title/message; audit events such as reaction.decision use their
own typed values. Observer deliveries are transient runtime records; generations are
configuration records retained indefinitely. Neither belongs inside HouseFact.
The generic module/API proposal and first EvidenceInstant slice remain unapproved.
For this synchronization, the developer required no planning-worktree edits: report
any exact contradiction/gap for their decision. Recheck current planning HEAD/status
and owning text on resumption; this checkpoint does not freeze the specs.

## Current implementation decisions

The user approved immutable dataclasses, one public `build_house_fact` construction
entry point and `FactBuildResult(fact, diagnostics)`; runtime delivers returned
diagnostics. Essential invalid content rejects construction, invalid evidence is
dropped with a diagnostic. The shared payload/codec first slice was subsequently approved and implemented;
full HouseFact assembly and later contracts remain to discuss. RFC 8785 is retained; CBOR is an alternative to evaluate if measured
performance problems justify it, not an automatic switch. Numeric domain is approved: non-boolean integers in ±(2**53-1), finite binary64
floats and no implicit numeric conversions. Owning-spec alignment is complete via CA4-96 (`15ccdcd`); rfc8785 0.1.4 was
subsequently approved and implemented in the first payload slice. Read NUMERIC_DOMAIN_HANDOFF.md. At planning `f52f86f`, Layer 0 §§7.4.1/9 add read-only
recovery occurrence and health/diagnostic handoffs to Layer 8 §10.3 projections,
without changing mechanisms or HouseFact fields; account for this consumer during
runtime design.

## Addendum checkpoint — planning `20bc9ae`

Read the six-item mapping in WORKING_CONTEXT for CA4-83/84/85 and the confirmed
CA4-82/80/79 rules. Room is owned by Layer 2 §2.6; Location keeps opaque references.
Opening has display_name metadata; ResolvedConnection has no access_type and is
derived from passable openings. Layer-5 catalog renames create a new layer generation
with the same Reaction configuration generation and no operational invalidation.
Display-name trim/NFC/case-fold collision checks never normalize stable identifiers.
Layer 8 is authoritative since `5f4cf1b`. The numeric domain was subsequently approved on 2026-10-13; coordinated
specification clarification was completed by Claude in `15ccdcd` (CA4-96). Do not edit planning here.

## Latest Layer 0/1 sync — 2026-10-14, planning `793b6a2`

This supersedes older checkpoints: reaction.decision.<digest> is now a per-Reaction
STATE, not an event (CA4-89); ReactionDecisionValue has no snapshot_id and includes
not_triggered/normal_exit. Removal/invalidation writes unavailable (CA4-95). Opening
has closed type/orientation vocabularies and no entity_id (CA4-92). Apply common
Layer-2 §2.7 name length/scoped uniqueness rules (CA4-91). Response ingress accepts
verified admin/resident and assigns matching source kinds; actor_ref stays governance
only. Accepted learned proposals commit through the composed atomic transaction
including review transition. Read the latest mapping in WORKING_CONTEXT.
At that checkpoint the numeric domain was not yet incorporated. The subsequent
CA4-96 update below resolves this pending alignment.

## Latest numeric-domain sync — 2026-10-14, `15ccdcd`

CA4-96 incorporates the approved numeric domain in Layer 1 §§3/4/4.3/10, with
references from Layer 0 §4.1 and Layer 5 §6.0 facet codec. Verification found no
discrepancy with NUMERIC_DOMAIN_HANDOFF.md. Structural checker: 96 CA4 issues, none
open, 128 contracts/72 reviews; no runtime tests. Numeric spec alignment is complete;
do not request it again. The subsequent first-slice entry below records the approved serializer and
implemented frozen-payload behavior; discuss the next contract after its review.

## First implementation slice — completed locally

The user approved rfc8785 0.1.4, private map/tuple deep freezing and the shared
payload/codec first slice, requested an instruction commit then implementation.
Instruction commit: `7ca1700`. The first behavioral slice now has canonical_json.py,
payloads.py, separate hashed runtime lock, tests, mutmut config and test evidence
in testing/PAYLOAD_CONTRACT.md. 109 tests pass; 265 mutants, 231 killed, 34 reviewed
as equivalent to the runtime contract, plus six killed module/decorator mutants.
No HouseFact assembly, HA adapter, storage or deploy exists yet. Changes from this
slice are not committed; inspect Git before continuing. Discuss the next contract
rather than resuming the old serializer-selection or numeric-pending proposals.

## Layer-0 temporal foundation — latest implementation scope

The user authorized proceeding with Layer 0. instants.py and timing.py implement
strict canonical time/duration/civil-field validation plus immutable Window, AtJob,
recurrence/CronEntry and CalendarWindow definitions. 201 tests total pass, 92 new;
188 timing mutants, 110 killed, 78 reviewed as contract-equivalent, seven targeted
module/decorator mutants killed. Read testing/TIMING_CONTRACT.md. Scheduler dispatch,
cycle clock, weekly next-due/DST execution and calendar cache are still pending.
This supersedes the earlier next action to ask whether to continue implementation.
All implementation changes remain uncommitted; preserve them. No spec edits/deploy.


## Critical review checkpoint — 2026-10-14

The implemented payload/codec and temporal foundation were reviewed against planning
9cd077e (clean). Fixed missing independent duration validation at IntervalRecurrence
admission (Layer 0 §3.1); see TIMING_CONTRACT.md for failing-before-fix and five-method
evidence. Current suite: 216 passed; 10 supplementary timing mutations killed;
Ruff/type/format pass. Earlier mutmut counts describe the preceding revisions.
All implementation/review changes remain uncommitted. Next work remains the
injected-clock monotonic scheduler; no HA runtime/storage completion is implied.


## Latest checkpoint — AtJob dispatcher

Payload/temporal/review block committed as e3e4314 at the user's request. The new
runtime/timing.py dispatcher and tests are local, uncommitted: 241 total tests pass;
95 new-scope mutants, 87 killed, 8 generic-error-prose survivors reviewed. Read
WORKING_CONTEXT and testing/ATJOB_DISPATCH.md. The injected monotonic timer port
has no concrete adapter yet. Cycle clock/discontinuities, diagnostic emission and
recurring next-due/DST execution remain pending; next action is Layer 0 §3.5.
Earlier uncommitted notes and scheduler-next notes are historical.


## Hardware portability steering

AtJobs must work correctly from Raspberry Pi to desktop hardware. Latest suite is
245 passing with simulated delayed callbacks and equal-deadline bursts; no actual
ARM/HA benchmark has run. Read WORKING_CONTEXT and ATJOB_DISPATCH.md: asyncio may
wake early by a clock-resolution, so the concrete timer adapter needs monotonic
minimum-deadline protection. Prioritize this adapter verification before the cycle
clock. No hardware-specific minimum, lateness/grace policy or device matrix was
approved. Pending dispatcher/test/docs changes remain uncommitted.


## Latest checkpoint — guarded asyncio timer

Dispatcher + delayed-callback tests committed as be83856. New asyncio monotonic
adapter/tests/evidence remain local and uncommitted. It guards early wakeups, avoids
busy waiting and preserves tiny positive delays at large uptimes. Read WORKING_CONTEXT
and MONOTONIC_ADAPTER.md: 286 tests pass including two real asyncio-loop cases;
117 scoped mutants, 92 killed, 25 contract-equivalent survivors reviewed. No HA/ARM
benchmark or lifecycle wiring exists yet. Next step returns to Layer 0 §3.5 cycle
clock/discontinuities; earlier adapter-pending notes are historical.


## Latest checkpoint — cycle clock/classification

Guarded asyncio timer block committed as beaac58. New runtime/clock.py/tests/evidence
are uncommitted: 319 tests pass, 125 scoped mutants (112 killed, 13 reviewed equivalent),
three supplementary mutations killed. Read WORKING_CONTEXT and CYCLE_CLOCK.md.
A backward adjustment can occur without any frozen cycle: -2 s correction between
60 s readings still advances wall 58 s. The §3.5 gap-start rule needs clarification;
see clarifications/CLOCK_GAP_BOUNDARIES.md. The user approved preparing this note for Claude; it is ready to hand off. No gap/diagnostic policy was invented or spec edited.
Independent next work: recurrence next-due/DST (§3.1); dependent gap wiring awaits
clarification. No HA clock adapter/engine integration/ARM benchmark yet.


## Latest checkpoint — CA4-98 resolved and applied

Planning dd89383 verified clean. The clock-gap ambiguity is resolved; the original
clarification note now records CA4-98. runtime/clock.py returns diagnostic/re-arm
requirements, detection point, corrected previous+1us floor position and immutable
gap intents with finish(tick). See current CYCLE_CLOCK.md: 336 tests pass; 198 mutants,
185 killed, 13 equivalent survivors reviewed; four supplemental mutants killed.
All clock changes remain uncommitted, latest commit beaac58. Persistence/emission/
periodic/re-arm wiring is still pending; computing end does not acknowledge a gap.
Next independent slice: internal recurrence next-due/DST (§3.1). Earlier clarification
pending notes are historical and no longer block this policy.


## Latest checkpoint — critical clock review

Fixed forward-jump gap bounds while cycle instants remain frozen; regression tests
failed first. Current suite 338 passes, fresh mutation 202 total/189 killed/13 reviewed
equivalent survivors, four supplements killed. Clock/review changes are uncommitted.
New separate clarification: §3.1's cycle-instant scheduling reference conflicts with
corrected-wall deadlines while §3.5 floors cycle time. Read
clarifications/CLOCK_SCHEDULING_REFERENCE.md before integrating those services.
CA4-98 remains resolved; no spec/scheduler-reference policy was silently changed.


## Latest checkpoint — CA4-99 applied

Planning d58431c verified clean. Scheduling-reference contradiction resolved: scheduler
now requires ExecutionClockReading(wall,cycle_instant); wall_clock uses raw wall,
elapsed uses floored cycle clock. CycleClock supplies captured pairs at cycle/periodic
comparison and read_execution between cycles without consuming state. Single-instant
API rejected, all local consumers migrated. Read CA499_EXECUTION_REFERENCES.md:
355 tests pass, 330 scoped mutants/301 killed/29 reviewed equivalent survivors,
five supplements killed. All clock-related changes remain uncommitted; last commit
beaac58. Actual HA/persistence/periodic/automatic re-arm wiring and ARM benchmarks are
still pending. Next independent slice: internal recurrence next-due/DST, choosing
reference by basis. Earlier ambiguity/API/evidence notes are historical.


## Latest checkpoint — weekly calculator, 2026-10-14

Committed the previously verified clock/CA4-98/review/CA4-99 changes as signed
commit 551caa7 (feat: add V3 cycle clock and basis-specific execution references).
This supersedes the preceding uncommitted-state notes; clean before this slice.
Planning rechecked clean at d58431c, read-only, including §§3.1/3.2 and Layer 1 §4.

Added runtime/recurrence.py::plan_weekly_job: pure weekly next-future-due calculation
using injected ZoneInfo and raw wall, preserving AtJob identity and wall_clock basis.
First fold only; missing local minutes map to first valid instant, with bounded binary
search rather than scanning seconds. Tests cover Rome spring/fall, 167/169-hour weeks,
Lord Howe half-hour gap, Apia skipped day, configured-vs-host civil dates, exact due
boundaries, invalid shapes, calendar exhaustion, and generated matching/future/floor
independence properties. Host timezone varied and restored in weekly tests.

407 total tests pass, 52 weekly cases including PBT, seed3145. Ruff check/format,
mypy and diff checks pass. Five-method evidence in testing/WEEKLY_RECURRENCE.md;
fresh mutmut 129 generated: 91 killed, 5 nontermination timeouts, 33 reviewed
equivalent survivors, exact diffs in WEEKLY_MUTANT_REVIEW.md. Default scope now
eight modules. No new test threshold or development/Git/deploy policy.

Developer authorized preparing the Claude prompt for the interval precision gap:
clarifications/INTERVAL_PRECISION.md. Valid Window(0.0000001) is lost by microsecond
deadline arithmetic; 1.5 µs is also inexact. Normative rejection/rounding/minimum and
numeric interpretation remain unresolved. No interval-next-due implementation or
shared-validator change. Do not silently choose a policy. No message sent to Claude.

This weekly slice and its docs remain uncommitted. It is a calculator, not the full
CronEntry service: automatic recurring re-arm, served-occurrence replay protection,
timezone-change coordination, HA wiring, durable configuration/gaps remain future
work. No HA/live/ARM benchmark or deployment claimed.

### Exact next action

Obtain Claude's normative interval representability handoff before implementing
interval due generation. Then build the bounded CronEntry lifecycle using the existing
paired clock API and monotonic dispatcher; explicitly protect weekly occurrence
identity during clock/timezone changes. Re-read current planning contracts first.
Git/deploy proposals still await review.


## Latest checkpoint — CA4-100 applied, 2026-10-14

Verified clean read-only planning HEAD 34ce913, normative owning/dependent sections
and registry/review. It resolves INTERVAL_PRECISION.md; note updated while retaining
historical prompt. contracts/deadlines.py adds derive_instant(anchor,Window,
strictly_after=False): canonical decimal, exact integer ratio, inclusive/strict
microsecond selection and overflow preflight. Immutable Unrepresentable carries
inputs for diagnostics. Window unchanged. runtime/recurrence.py adds plan_interval_job
(cycle_instant/elapsed) and register_interval_job for one guarded admission;
overflow returns diagnostic input without changing timers. Caller must publish it.
Weekly calculation unchanged; no existing float-seconds timedelta producer to migrate.

445 V3 tests pass, 38 new, seed3145; lint/format/mypy/diff pass. Five-method evidence
in testing/CA4100_DEADLINES.md. Fresh mutation: 239 generated, 180 killed, 5 unchanged
weekly timeouts, 54 equivalents (21 new prose/ASCII aliases, 33 reviewed weekly),
exact diffs in CA4100_MUTANT_REVIEW.md. Supplement frozen diagnostic mutant killed.
Default scope nine modules. No new dependency/policy. Weekly and CA4-100 changes
remain uncommitted; last signed commit 551caa7.

Full CronEntry automatic lifecycle, served-occurrence protection, HA timezone wiring,
diagnostic publication, CalendarViewRequirement staging and persistence remain
unimplemented. Their acceptance gates have not run; no HA/live/ARM/deploy claim.
Future owner deadlines/horizons must use derive_instant; L2 strict and L5 whole-ms
rules remain valid.

### Exact next action

Proceed to bounded CronEntry lifecycle above existing single-arm planners and
AtJobScheduler: recurring re-arm, callback failure isolation and served-weekly
occurrence protection during clock/timezone changes. Re-read current Layer 0
§3.1/§3.5/§9/§13 first and surface any missing policy. Static calendar horizon
staging and diagnostic publication belong to future coordinators/adapters.
Git/deploy proposals remain pending review.


## Latest checkpoint — standing interval lifecycle, 2026-10-14

Committed all verified weekly and CA4-100 changes at user request: signed b2bff62,
feat: add V3 recurrence planning and exact deadline construction. Clean before this
slice. Earlier uncommitted notes are superseded. Planning rechecked clean 34ce913,
read-only; Layer 0 §3.1/§3.5/§9/§10/§13 apply.

Added runtime/interval_recurrences.py::IntervalRecurrences for standing interval
rules. It uses the existing planners and shared monotonic dispatcher, explicit fresh
clock capture and non-raising diagnostic sink. Callback failures are diagnosed and
finally re-arm the current rule; reentrant cancel/stop/replacement cannot resurrect
an older rule. Replacement admission failure preserves accepted state. Overflow
is reported before changing timers. Re-arm infrastructure failure/overflow retains
the standing definition with no pending timer and an explicit diagnostic; no retry
policy invented. Stop cancels only owned registrations; restart from supplied rules
arms fresh from now, without recovering countdowns.

469 tests pass, 24 new, seed3145; Ruff lint/format, mypy and diff pass. Five-method
matrix in testing/INTERVAL_LIFECYCLE.md. Fresh mutmut: 119 generated, 107 killed,
12 generic-prose equivalents, no timeout/error/skipped; exact diffs in
INTERVAL_LIFECYCLE_MUTANT_REVIEW.md. Three public diagnostic frozen-record mutants
killed by mutation_interval_recurrences.py with a passing baseline. Default scope
now ten modules. No new dependency, policy or timing threshold.

New lifecycle slice remains uncommitted; last signed commit b2bff62. Not yet a full
CronEntry service: weekly served-occurrence protection and timezone updates are
pending. Persistence of standing rules and automatic HA restart restoration,
HA diagnostic logging/publication, one-shot callback fault-boundary integration,
calendar staging and clock coordinator remain future work. No live HA/ARM/deploy
claim. Diagnostic sink must log/publish promptly without raising; this service does
not silently swallow infrastructure sink failures.

### Exact next action

Review the interval lifecycle before committing its slice, then implement weekly
lifecycle and served-occurrence identity/timezone re-arm against current Layer 0
§3.1/§3.5/§9/§13. Keep basis-specific references and CA4-100 deadline rule. Clarify
any missing occurrence policy through the existing Claude workflow rather than
choosing silently. Git/deploy proposals remain pending developer review.
