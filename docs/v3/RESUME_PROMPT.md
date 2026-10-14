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
dropped with a diagnostic. Concrete modules/API details and first code slice remain
to agree. RFC 8785 is retained; CBOR is an alternative to evaluate if measured
performance problems justify it, not an automatic switch. Numeric domain is approved: non-boolean integers in ±(2**53-1), finite binary64
floats and no implicit numeric conversions. Owning-spec alignment is complete via CA4-96 (`15ccdcd`); library selection remains
pending. Read NUMERIC_DOMAIN_HANDOFF.md. At planning `f52f86f`, Layer 0 §§7.4.1/9 add read-only
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
do not request it again. Next discuss concrete serializer/library/version and frozen
payload implementation, then approve the first behavioral code slice.
