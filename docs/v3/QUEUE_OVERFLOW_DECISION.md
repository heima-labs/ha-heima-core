# V3 retry queue: irreducible overflow decision

**Status:** Developer approved the global gap on 2026-10-12 and progressive recovery on 2026-10-13; normative correction is CA4-70 in the planning worktree. This file preserves the research rationale; Layer 0 §§4.4/4.6 own the contract.
**Checked:** 2026-10-13 against planning commit `f84d4e7`, which contains the CA4-70 progressive recovery correction: 7 layers, 114 mapped contracts, 77 CA4 issues, none open.

## Original gap before CA4-70

Before CA4-70, Layer 0 §4.6 budgeted the pending durable queue at `max(32 MiB, 5% × effective_memory_limit)`, forbids blocking admission, and discards superseded state transitions followed by oldest event facts. It also required the latest queued state per key and continuity/gap boundaries are never discarded. A sufficiently large number of distinct state keys and boundaries can exceed any finite budget with no eligible item left to discard. That text gave no legal next transition. The outbox does not solve this: it uses the same unavailable storage and is a separate durability contract.

## Comparable systems (primary sources)

| Project | Full or unavailable destination | Transfer to V3 |
|---|---|---|
| [Telegraf](https://docs.influxdata.com/telegraf/v1/concepts/data-pipeline/) | Bounded memory buffer drops oldest metrics; an optional disk buffer retains across restart but has no disk-space limit. | Supports explicit oldest-loss under a hard memory bound; does not model a current-state claim or per-stream historical completeness. |
| [OpenTelemetry Collector](https://go.opentelemetry.io/collector/exporter/exporterhelper) | Sending queue rejects and counts failed enqueues by default when full; blocking is opt-in. Persistent queue also fails when storage cannot accept data. | Supports observable loss and separation of admission from retry; rejecting a V3 fact would conflict with the approved no-blocking current-cycle design. |
| [Vector](https://vector.dev/docs/architecture/buffering-model/) | A terminal buffer either blocks or drops. Disk overflow does not remove the need for a terminal choice; a documented overflow topology can change ordering. | Confirms there is no unlimited-lossless finite queue during an outage; V3 needs ordered history and cannot casually add a second spill queue. |
| [Prometheus remote write](https://prometheus.io/docs/practices/remote_write/) | Memory queue stops reading its local WAL when full; the WAL eventually compacts and undelivered data is lost after a prolonged outage. | Its upstream WAL lets it delay loss, but V3's SQLite target itself is the failed store, so that escape route is unavailable. |
| [Home Assistant Recorder runs](https://data.home-assistant.io/docs/recorder/) | Run metadata marks an incorrectly closed run, letting consumers distinguish uncertain history after restart. | Supports conservative coverage boundaries after a crash, but is not a queue overflow policy. |

Additional recovery analogues reviewed in the discussion: [Kubernetes list/watch](https://kubernetes.io/docs/reference/using-api/api-concepts/) invalidates a cache and relists when event history expires, then resumes from a versioned boundary; [etcd recovery](https://etcd.io/docs/v3.5/op-guide/recovery/) invalidates watcher caches after snapshot restore. They support explicit baseline invalidation and resynchronization, but HA cannot reconstruct every lifecycle claim from a state snapshot.

These sources establish the trade-off and recovery patterns, not a direct product rule for Heima.

## Approved resolution

**Approved:** keep the hard budget and uninterrupted admission. After the existing two discard stages, if protected items alone exceed the budget, enter one exceptional *global queue-overflow epoch*: retain a fixed-size global earliest-loss boundary; collapse existing per-stream pending loss metadata into it; discard oldest remaining queued facts as needed, including previously protected latest states; keep the most recent items that fit. Report every history request intersecting that epoch as incomplete with `queue_overflow`, including state reconstruction. Keep the live current index and short-term buffer for the running process. After storage recovers, commit the global boundary before or with retained items; do not treat old durable state as current across it. Close the global gap at a fresh complete HA intake and acknowledged full-cycle accounting boundary, even when individual keys are still unrecovered. Re-seed valid producer assertions progressively through the existing bounded queue and atomic cycle batches; a key becomes durably usable only after its baseline acknowledgement. Unseeded required keys remain unknown and historically incomplete with `queue_overflow` after global closure. An undefined HA state supplies an unavailable assertion under the existing source rules; lack of durable proof alone does not alter live availability. A crash before the boundary is durable is covered by the unadvanced continuity watermark/process-interruption rule. One bounded global boundary prevents per-stream metadata from becoming a second unbounded queue.

Layer 0 §§4.4/4.6, Layer 3 §4.4.2 and CA4-70 now specify the ordering, re-seeding and acceptance cases. This fallback deliberately weakens the ordinary promise to retain every latest queued state, only in the mathematically irreducible case; it must be explicit in Layer 0 and reviewed with Layer 3 historical consumers.

**Alternative A:** reject a staged configuration unless its worst-case protected queue footprint fits the minimum 32 MiB budget. This preserves the existing protected-item rule but adds a product limit on state identities, projections and gap metadata, and may be difficult to prove for dynamic producers.

**Alternative B:** allow protected items to exceed the budget temporarily. This preserves their retention but makes the declared queue budget nonbinding during a prolonged outage, reopening CA4-38's resource risk.

Alternatives A and B were not selected. The approved rule is in the planning worktree; no V3 runtime implementation or test exists yet.

## Approved recovery boundaries

No generic fallback restores an invalidated old state as current. The desired-target Recovery checkpoint is a separate existing contract. A lifecycle claim requires owner proof; a fresh HA active reading cannot recreate a managed opening. Recovery-only unchanged baseline records add no duplicate live-buffer change, physical edge, hold or committed-state-observer delivery. Repeated irreducible loss advances baseline invalidation; closure and per-key acknowledgements survive restart. Exact SQLite schema, queue/writer classes and recovery scheduling limits remain implementation work.
