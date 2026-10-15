# Claude prompt — weekly occurrence identity across clock/timezone changes

Status: resolved by **CA4-101 / planning 0b82d61**, verified 2026-10-15.
Original prompt retained below as history. No planning edits by Codex.

Initial V3 has interval-only CronEntry; no generic weekly lifecycle or served-date
ledger belongs to Timing. WeeklyRecurrence remains a value type and pure occurrence
calculation, retaining requested date and canonical physical start. Presence-simulation
session identity belongs to its Layer-5 activation (requested date; served-date RAM;
merged starts; no catch-up; restart restores no activation). See Layer 0 §3.1/§13,
Layer 5 §7.2/§7.2.1 and testing/CA4101_OCCURRENCES.md.

## Prompt

Read current Layer 0 §3.1, §3.5, §9 and §13 before changing the planning worktree.
Current approved rules: first-fold execution only, no second execution for the
same civil weekly request; timezone changes re-arm between cycles without replay
of a past weekly occurrence; duplicate (owner,job_id) registration replaces;
restart recovers only the standing definition, not an interrupted countdown.
The existing pure next-due calculator already applies missing-time/first-fold rules.

The lifecycle needs a precise definition of which civil request was served. UTC
next-due alone cannot establish this after a timezone change. Concrete example:
Monday 2026-10-19, 07:00 Europe/Rome executes at 05:00 UTC. At 05:01 UTC the
configured zone becomes UTC. The same Monday's 07:00 is now future. A fresh
next-due calculation arms it and can run the routine twice for that civil date.
Is that the same already-served occurrence under the no-replay rule? The text
requires no replay, but does not define its identity or the scope of memory.

Other cases that distinguish implementations:

1. First-fold request executed; clock regresses into the period before its first
   occurrence; post-callback next-due calculation can select that same request again.
2. A skipped civil date: Pacific/Apia Friday 2011-12-30 04:00 maps to Saturday
   2011-12-31 00:00. UTC due or actual local delivery date loses the requested date.
3. Same (owner,job_id) re-registered after execution with identical pattern, changed
   label/callback, or a different weekday/hour/minute. Which replacements preserve
   served-occurrence identity, and which start a new rule? Do not infer an answer
   merely from timer replacement semantics.
4. Delayed delivery crosses later matching civil requests. They are not implicitly
   caught up; specify how this relates to served identity rather than treating them
   as actual firings.
5. Multiple zone changes or large backward corrections can revisit earlier dates.
   Must a bounded watermark suppress all earlier civil dates, only actual served
   requests, or another rule? Which storage is required? Keep restart's existing
   standing-definition-only semantics unless a product decision changes it.
6. Two requested weekdays can map to the same physical due across a skipped day;
   say whether one arm serves both requests or how collisions are handled.

Requested outcome: define transient occurrence identity, consumption moment (including
callback failure), replacement scope, clock/timezone behavior and bounded memory;
clarify how requested civil date differs from due/delivery date. Add acceptance
examples for these cases, reconcile registry/backlog/review through the standard
workflow, and return exact normative sections. Do not introduce a second instant
wire form, catch-up, arbitrary retention horizon or durable countdown recovery.

Codex committed interval lifecycle as f92639a. Weekly next-due calculation exists,
but full weekly lifecycle and zone-change replay protection await this clarification.
Independent callback fault isolation is being made reusable while that policy is open.
