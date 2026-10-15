# Prompt to resume V3 implementation

> Claim primitives committed asf5f2369. New composed producer staging is
> uncommitted: all15 core reservations, duplicate static identities, inventory
> reference checks and immutable staged type bindings.1567 tests,Ruff/mypy pass.
> Read latest WORKING_CONTEXT and testing/PRODUCER_STAGING.md and PRODUCER_STAGING_MUTANTS.md.
> resolve_type is staging-only; bindings do not prove source/actor/generation
> authority. Next: concrete producer ports/admission tied to active generation,
> then coordinator order and acceptance. Index/queue/fact-marker SQL pending.
> Planningaa4455a read-only; Topology CA4-104 belongs to a later slice.

> **Current state — 2026-10-15, CA4-101:** CronEntry is interval-only. Use
> next_weekly_occurrence(pattern,now,zone) for civil occurrences, not plan_weekly_job.
> Weekly identity is resolved at the L5 activation; do not build a generic weekly
> lifecycle. The last checkpoint below supersedes historical state/next-action notes.

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


## Latest checkpoint — shared callback boundary / weekly clarification, 2026-10-14

Committed verified interval lifecycle at user request as signed f92639a,
feat: add V3 standing interval recurrence lifecycle. Clean before this slice;
earlier uncommitted-state notes superseded. Planning checked clean/read-only at
34ce913, Layer 0 §3.1/§3.5/§9/§10/§13.

Found missing weekly occurrence identity rules for timezone changes and replacement.
Example: Monday 07:00 Rome served at 05:00 UTC; switch to UTC at 05:01 makes that
Monday 07:00 future again. Spec says no replay without defining identity/memory.
Requested civil date also differs from delivered date for skipped-day gaps; a backward
clock correction can revisit a served request. User authorized the Claude prompt:
clarifications/WEEKLY_OCCURRENCE_IDENTITY.md. No planning edit/message sent, no new
identity/reset/retention policy chosen. Full weekly lifecycle remains dependent.

Completed independent shared callback isolation: runtime/job_callbacks.py with
JobCallbackFault, invoke_job_callback and isolate_job_callback. Intervals reuse it
within existing finally re-arm; existing interval-module import remains valid.
One-shot wrapper integration proves a failed job is consumed once and other owners
continue. Diagnostic infrastructure errors and BaseException control signals propagate.
Actual coordinator must use the wrapper; low-level dispatcher behavior unchanged.
Updated supplementary lifecycle mutation runner for diagnostic-class relocation.

479 V3 tests pass, 10 new, seed3145; lint/format/mypy/diff pass. Five-method evidence
in testing/JOB_CALLBACK_BOUNDARY.md. Fresh mutmut on both changed modules: 144 generated,
124 killed, 20 generic-prose equivalents, no timeout/error/skipped; exact diffs in
JOB_CALLBACK_MUTANT_REVIEW.md. Three frozen public-record supplement mutants killed.
Default scope eleven modules. No new dependency/policy, live HA/ARM/deploy claim.
This new callback slice and clarification remain uncommitted; last signed commit f92639a.

### Exact next action

Obtain Claude's normative handoff defining weekly occurrence identity, consumption,
replacement scope, clock/timezone behavior and bounded transient memory before
implementing that dependent lifecycle. Keep existing first-fold/gap calculator,
CA4-98/99 basis rules and CA4-100 duration construction. Future HA diagnostic wiring,
calendar staging and durable configuration remain unimplemented. Git/deploy proposals
still await developer review.


## Latest checkpoint — CA4-101 applied, 2026-10-15

Verified clean read-only planning HEAD 0b82d61, normative L0 §3.1/restart/§13,
L5 §7.2/§7.2.1 and CA4-101 registry/review. Weekly CronEntry is OUT of Initial V3,
not a blocked feature. Clarification WEEKLY_OCCURRENCE_IDENTITY.md marked resolved.

contracts/timing.py now types/validates CronEntry.pattern as IntervalRecurrence only;
RecurrencePattern removed. Runtime interval gates reject reconstructed legacy weekly
entries. Existing interval lifecycle and shared callback isolation unchanged.
Removed internal plan_weekly_job (only test consumers); replaced with pure
next_weekly_occurrence(pattern,canonical_now,ZoneInfo) -> frozen WeeklyOccurrence
(requested_date: civil date, start: EvidenceInstant). No job metadata or paired-clock
parameter; consumers use the raw wall reference and build wall_clock AtJob boundaries.
Requested civil date survives missing-time resolution, including Apia's skipped day;
merged physical starts retain distinct requested dates for L5 to consume. No native
datetime instant crosses the output boundary; civil date is an in-process value.

486 V3 tests pass, seed3145; Ruff lint/format, mypy and diff pass. New rejection
regression failed on prior code as expected. Evidence in CA4101_OCCURRENCES.md.
Fresh mutmut timing+recurrence: 305 generated, 210 killed, 5 known search timeouts,
90 equivalents (80 generic prose, 1 cast, 9 search variants), exact diffs in
CA4101_MUTANT_REVIEW.md. Supplements: 10 timing mutants and 2 weekly occurrence
mutants killed, clean baselines. Default scope stays eleven modules, no dependency
or policy change. Newer two merged-date test instances added after mutation/source
freeze. No live HA/ARM/deploy claim.

CA4-101 and prior shared-callback changes remain uncommitted; last signed f92639a.
No L5 activation/session implementation exists: served-date RAM, equal-start merge,
late session remaining-time admission, timezone re-arm and restart activation rules
are now specified and must be implemented THERE. No generic weekly lifecycle next.

### Exact next action

Review/commit shared callback and CA4-101 slices when requested; continue Layer 0
integration with actual clock/coordinator/HA diagnostic ports and periodic interval
wiring, or the next agreed bounded foundation contract. Calendar staging, persistence
of standing configuration and durable gaps remain future work. Do not schedule a
weekly CronEntry or implement a Timing-level served-date ledger. L5 session fixtures
belong to the future presence-simulation activation. Git/deploy proposals still pending.


## Latest checkpoint — timing clock bridge, 2026-10-15

Committed shared callback and CA4-101 changes at user request as signed f182a37,
feat: align V3 recurrence contracts and share callback fault isolation. Clean before
this slice. Planning clean/read-only at 0b82d61, Layer 0 §3.1/§3.5/§4.4/§13 and
fault/diagnostic sections checked. Interval-only CronEntry scope is unchanged.

Added adapters/ha/clock_source.py SystemClockSource for sequential raw UTC/monotonic
host capture; runtime/timing_clock.py TimingClock uses explicit source, CycleClock,
scheduler, observation and re-arm-fault ports. Each comparison samples once and
re-arms civil jobs from its exact raw wall; execution reads change no baseline.
Observer receives classification/gap intents before scheduler effects. Tests compose
the periodic entry point with an ordinary 60-second IntervalRecurrence, outside a
cycle, without duplicate jump detection. Actual continuity writer is not created.

Found/fixed an actual scheduler safety defect: failed re-arm used to retain a stale
pre-correction timer that could execute before corrected wall due. Reproducer failed
before fix. rearm_wall_clock now returns per-job immutable failures, cancels failed
old arms, continues other civil jobs, and leaves elapsed untouched; bridge reports
each failure with comparison/job context. Normal registration failure still preserves
its valid old arm. No retry/fallback policy invented. All runtime callers inspected.

502 V3 tests pass, 16 new, seed3145; Ruff lint/format, mypy/diff pass. Evidence in
TIMING_CLOCK_BRIDGE.md. Fresh mutmut on three affected modules: 168 generated,
156 killed, 12 equivalent generic-error-prose survivors, no timeout/error/skipped;
exact diffs in TIMING_CLOCK_MUTANT_REVIEW.md. Three frozen-result supplement mutants
killed by mutation_timing_clock.py, clean baseline. Default scope thirteen modules.
No new dependency, timing threshold or policy; no HA/live/ARM/deploy claim.

New bridge/fix remains uncommitted; last signed f182a37. Observe/report ports require
prompt non-raising in-memory effects/logging/queuing, not waiting for storage. Their
actual runtime/HA implementations, durable gap state/acknowledgement, continuity
watermark worker, standing configuration persistence and calendar staging remain
future work. Sequential host capture is not an atomic clock pair. A gap completion
intent never certifies durable acknowledgement.

### Exact next action

Review/commit this bridge slice when requested. Continue with concrete Layer-0
continuity metadata ownership and persistence contract before wiring real durable
gap/periodic watermark effects; alternatively the next agreed foundation contract.
Actual HA bootstrap/shutdown and fault publication need their own bounded integration
slice. Preserve shared 60-second CronEntry ownership, CA4-98/99 references and CA4-101
interval-only scope. Git/deploy proposals remain pending developer review.


## Latest checkpoint — observation coverage foundation, 2026-10-15

Committed verified clock/scheduler bridge and safe failure handling at user request
as signed 6a60bd5, feat: connect V3 clock observations to safe scheduler rearming.
Clean before this slice. Planning clean/read-only 0b82d61, L0 §4.4 continuity value,
required-stream composition and dependency registry checked. Older bridge-uncommitted
notes are superseded.

Added contracts/observation.py with closed ObservationCoverageStatus/ObservationGapReason,
validated frozen ObservationCoverage, and combine_observation_coverage(process,
required_streams=()). Complete/incomplete field invariants, exact closed reason shape,
ASCII order/distinctness and canonical missing instant validated. Composition unions
reasons and keeps earliest missing instant, revalidating reconstructed inputs.
Process result is mandatory even for zero required streams; known gaps cannot be
healed by complete streams. No clipping, endpoint or retention policy is invented.

541 V3 tests pass, 39 new, seed3145; Ruff lint/format, mypy and diff pass. Five-method
evidence in OBSERVATION_COVERAGE.md. Fresh mutmut: 115 generated, 67 killed, 48 generic
error-prose equivalents, no timeout/error/skipped; exact diffs in
OBSERVATION_MUTANT_REVIEW.md. Three supplemental observation mutations killed with
clean baseline (frozen result, dropped declared reason, accepted unknown reason).
A rejected collection-error probe was not counted as a behavioral kill. Default
scope fourteen modules. No new dependency, policy or SQLite schema; no live/HA/ARM/
durable gap acknowledgement/deploy claim.

New coverage slice remains uncommitted; last signed 6a60bd5. Its inputs must already
cover the same request and be clipped to it, with only required streams selected.
This algebra does not certify trusted metadata, store gaps, select interval endpoints,
resolve latest state availability, evaluate retention or acknowledge writes. Those
belong to the future timeline/read implementation. HistoricalReadResult and HouseFact
assembly remain unimplemented.

### Exact next action

Review/commit this value/composition slice when requested. Continue the bounded
Layer-0 observation timeline/read path: derive request-clipped process/stream coverage
from specified gap and durability state before connecting SQLite writer/acknowledgement.
Read current §4.1/§4.4/§4.6 and dependencies; surface ambiguous endpoint cases instead
of choosing silently. HA lifecycle/diagnostics, watermark writer and standing config
persistence remain future work. Preserve interval-only CronEntry and current clock
rules. Git/deploy proposals remain pending developer review.


## Latest checkpoint — historical intervals and critical review, 2026-10-15

Committed observation coverage at user request as signed 0cc0929, feat: add V3
observation coverage contracts and conservative composition. Clean before this slice.
Planning checked clean/read-only 0b82d61, L0 §4.4/§13 and timing §3.1/§3.5.

Added contracts/history_intervals.py: explicit bounded canonical endpoints and inclusion
flags; point/empty intervals on microsecond grid; exact intersection or None. Inputs
revalidated, endpoint convention never chosen implicitly. This is geometry for later
request-clipped gap evaluation, not durable-gap/metadata assessment or a complete
historical read. No open-gap closure or write acknowledgement is inferred.

Then performed requested critical review of 0cc0929,6a60bd5,f182a37,f92639a and timing
consumers/dependencies. Two confirmed defects fixed after 8 regression instances
failed: (1) timedelta.total_seconds float transport could shorten canonical duration;
new shared _countdown uses integer µs + least non-early float, no due/Window change;
(2) past year-1 local candidate could overflow UTC and hide a valid next-week start;
civil past-candidate prefilter avoids conversion and retains physical UTC fold check.
Updated four old tests to exact Fraction transport bounds rather than binary nominal
float equality; no approximate tolerance. Full report CRITICAL_REVIEW_20261015.md.

Third reproduced case needs spec decision: forward correction while old backward
floor holds has different new-gap completion for cycle vs periodic detection.
Developer approved prompt clarifications/PERIODIC_FORWARD_GAP_DURING_FREEZE.md.
ClockGap/CycleClock unchanged pending handoff; no hidden xfail or product policy.

587 V3 tests pass, seed3145; lint/format/mypy/diff pass. Five-method evidence in
HISTORY_INTERVALS_AND_REVIEW.md. Fresh mutmut on three affected modules: 364 generated,
291 killed, 5 known civil-search timeouts, 68 reviewed equivalents, exact diffs in
HISTORY_INTERVAL_REVIEW_MUTANTS.md. Supplements: 5 interval (including property logic
excluded by mutmut) and 2 weekly occurrence mutants killed, clean baselines. Default
scope fifteen modules. No new dependency/policy/live HA/ARM/SQLite/deployment claim.

New interval geometry/review fixes/prompt remain uncommitted; last signed 0cc0929.
HA lifecycle/diagnostic ports, SQLite writer, durable metadata/acknowledgement and
full history assessment remain future work. Review is scoped local evidence, not
proof of full engine integration or performance.

### Exact next action

Deliver approved prompt to Claude via developer; obtain normative forward-periodic-
under-freeze rule before changing that gap path. Review/commit current geometry and
review fixes when requested. Continue request-scoped observation assessment only
from explicit endpoint/trust/durability inputs; do not infer empty history or continuity
from missing metadata. Preserve interval-only CronEntry and no generic weekly lifecycle.
Git/deploy proposals remain pending developer review.
