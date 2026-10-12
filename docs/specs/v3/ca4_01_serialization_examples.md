# CA4-01 serialization examples (approved A1/B1/C2)

These are complete value/projection payloads, not complete surrounding `HouseFact` records. The light case uses a configured `security.presence_simulation` Reaction; the HVAC case uses a configured `environment.planned_comfort_trajectory` Reaction with the Initial-V3 `hvac_state.trajectory_setpoint.v1` target. Both Initial-V3 descriptors use `next_reaction_step`: their shown hold anchors are previously confirmed scheduled steps, not expiry deadlines. The illustrated `normal_exit` follow-ups occur after a verified cancellation before another target-changing step. The valve case is a **shape-only example for a possible future descriptor**, not an executable Initial-V3 configuration: no Initial-V3 irrigation descriptor has a `normal_exit_contract`. It demonstrates generic serialization and per-channel identity, not Initial-V3 outcome eligibility. All identifiers and facet names are ASCII, so the shown compact JSON byte count equals its character count. Values use RFC-8785 canonical JSON text as a **string** within the containing JSON. The canonical LocationKey JSON text is likewise a scalar `subject` in the persisted intent; the transient typed intent and the fact `where` use a validated `Location`. Collection depth counts the normalized dataclass field object as 1, its map/tuple fields as 2, and no collection inside a field. The expected/observed fingerprints below are illustrative 64-hex normalized-state fingerprints; their producer checks the binding's fingerprint contract independently. The hold transition operation ids are distinct 64-hex opaque identifiers, separate from the hold ids; the follow-up operation ids are SHA-256 of the exact B1 domain-prefixed canonical identity arrays.

| Case | `HoldLifecycleValue` bytes/depth | `ReactionFollowUpIntent` bytes/depth | `OperationalEventValue` bytes/depth |
|---|---:|---:|---:|
| light | 1827 / 2 | 763 / 2 | 891 / 2 |
| valve (future descriptor shape only) | 1289 / 2 | 694 / 2 | 786 / 2 |
| hvac (Initial V3) | 1345 / 2 | 747 / 2 | 856 / 2 |

The format check rejects a nested `context.expected_facets`, a composite facet inserted directly into a depth-two map, noncanonical facet text, and any staged adapter/Reaction combination whose **worst-case** complete inline audit or follow-up payload exceeds depth 2 or 8 KiB. These small examples do not replace that staging proof. The value-level size excludes `HouseFact` metadata and outbox storage indexes.

## light

`HoldLifecycleValue`:

```json
{"actuator_id":"light.living_1","anchor_step_id":"session-01-episode-3-on-light.living_1","anchor_target_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","controlled_channel":"light_state","divergent_facets":["brightness","color","power"],"event":"activated","expectation_activation_ids":{"brightness":"activation-42","color":"activation-42","power":"activation-42"},"expectation_generation_ids":{"brightness":"gen-7","color":"gen-7","power":"gen-7"},"expectation_reaction_ids":{"brightness":"presence_simulation","color":"presence_simulation","power":"presence_simulation"},"expectation_step_ids":{"brightness":"session-01-episode-3-on-light.living_1","color":"session-01-episode-3-on-light.living_1","power":"session-01-episode-3-on-light.living_1"},"expectation_target_fingerprints":{"brightness":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","color":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","power":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"expected_fingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","expected_values":{"brightness":"0.7","color":"[255,128,0]","power":"true"},"expires_at":null,"hold_id":"hold-light-01","invalidation_reason":null,"observation_context":"normal","observed_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","observed_values":{"brightness":"0.4","color":"[255,80,0]","power":"false"},"operation_id":"092dc6787dd5ba818378745a4815be8d4972cfd2df8fc4fea1db442b4bdc2bc7","origin":"resident_manual","origin_evidence":"direct_authenticated_command","reaction_activation_id":"activation-42","reaction_generation_id":"gen-7","reaction_id":"presence_simulation","release_mode":"next_reaction_step","release_reason":null,"scope":"channel"}
```

Persisted `ReactionFollowUpIntent`:

```json
{"actuator_id":"light.living_1","configuration_generation_id":"gen-7","controlled_channel":"light_state","expected_facets":{"brightness":"0.7","color":"[255,128,0]","power":"true"},"hold_id":"hold-light-01","later_step_remains":false,"observation_available":true,"observation_epoch_id":"epoch-9","observed_at":"2026-10-03T20:00:00.000000+00:00","observed_facets":{"brightness":"0.4","color":"[255,80,0]","power":"false"},"operation_id":"8ab6a81f49c79d9b268d4de9a3dcfef8f7cf60f5431b40178d2bf6b66c2cc3bc","path":"normal_exit","planned_step_id":null,"prepared_at":"2026-10-03T20:00:01.000000+00:00","reaction_activation_id":"activation-42","reaction_descriptor_id":"security.presence_simulation","reaction_id":"presence_simulation","subject":"[\"room\",\"living\"]"}
```

`OperationalEventValue` for `reaction.follow_up`:

```json
{"context":{"actuator_id":"light.living_1","configuration_generation_id":"gen-7","controlled_channel":"light_state","expected.brightness":"0.7","expected.color":"[255,128,0]","expected.power":"true","hold_id":"hold-light-01","later_step_remains":false,"observation_available":true,"observation_epoch_id":"epoch-9","observed.brightness":"0.4","observed.color":"[255,80,0]","observed.power":"false","observed_at":"2026-10-03T20:00:00.000000+00:00","operation_id":"8ab6a81f49c79d9b268d4de9a3dcfef8f7cf60f5431b40178d2bf6b66c2cc3bc","outcome":"ended_without_final_target","path":"normal_exit","planned_step_id":null,"reaction_activation_id":"activation-42","reaction_descriptor_id":"security.presence_simulation","reaction_id":"presence_simulation"},"context_version":1,"notification_key":"reaction.follow_up:8ab6a81f49c79d9b268d4de9a3dcfef8f7cf60f5431b40178d2bf6b66c2cc3bc","severity":"warning"}
```

## valve

This `example.future_valve_program` Reaction and its `normal_exit` are illustrative
protocol inputs only. Initial V3 has no descriptor that can activate this case.

`HoldLifecycleValue`:

```json
{"actuator_id":"valve.garden_1","anchor_step_id":null,"anchor_target_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","controlled_channel":"valve_position","divergent_facets":["position"],"event":"activated","expectation_activation_ids":{"position":"activation-9"},"expectation_generation_ids":{"position":"gen-3"},"expectation_reaction_ids":{"position":"example.future_valve_program"},"expectation_step_ids":{},"expectation_target_fingerprints":{"position":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"expected_fingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","expected_values":{"position":"1"},"expires_at":"2026-10-03T20:30:00.000000+00:00","hold_id":"hold-valve-01","invalidation_reason":null,"observation_context":"normal","observed_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","observed_values":{"position":"0.5"},"operation_id":"c36e3368e6d634fad79c04ffddbcd8ff560fd9a867e490689148d61db0e3ff55","origin":"resident_manual","origin_evidence":"direct_authenticated_command","reaction_activation_id":"activation-9","reaction_generation_id":"gen-3","reaction_id":"example.future_valve_program","release_mode":"fixed_duration","release_reason":null,"scope":"channel"}
```

Persisted `ReactionFollowUpIntent`:

```json
{"actuator_id":"valve.garden_1","configuration_generation_id":"gen-3","controlled_channel":"valve_position","expected_facets":{"position":"1"},"hold_id":"hold-valve-01","later_step_remains":false,"observation_available":true,"observation_epoch_id":"epoch-9","observed_at":"2026-10-03T20:00:00.000000+00:00","observed_facets":{"position":"0.5"},"operation_id":"29185c11d5713df8447cf5228f366d6868594c3e0473d07f22b9f49944ba99a5","path":"normal_exit","planned_step_id":null,"prepared_at":"2026-10-03T20:00:01.000000+00:00","reaction_activation_id":"activation-9","reaction_descriptor_id":"example.future_valve_program","reaction_id":"example.future_valve_program","subject":"[\"room\",\"garden\"]"}
```

`OperationalEventValue` for `reaction.follow_up`:

```json
{"context":{"actuator_id":"valve.garden_1","configuration_generation_id":"gen-3","controlled_channel":"valve_position","expected.position":"1","hold_id":"hold-valve-01","later_step_remains":false,"observation_available":true,"observation_epoch_id":"epoch-9","observed.position":"0.5","observed_at":"2026-10-03T20:00:00.000000+00:00","operation_id":"29185c11d5713df8447cf5228f366d6868594c3e0473d07f22b9f49944ba99a5","outcome":"ended_without_final_target","path":"normal_exit","planned_step_id":null,"reaction_activation_id":"activation-9","reaction_descriptor_id":"example.future_valve_program","reaction_id":"example.future_valve_program"},"context_version":1,"notification_key":"reaction.follow_up:29185c11d5713df8447cf5228f366d6868594c3e0473d07f22b9f49944ba99a5","severity":"warning"}
```

## hvac

`comfort_trajectory_bedroom` is a configured Reaction using the Initial-V3
`environment.planned_comfort_trajectory` descriptor. Its target has only
`mode="heating"` and `setpoint_c`; the resident changes the latter while the
mode remains matched. No fan-speed target is implied.

`HoldLifecycleValue`:

```json
{"actuator_id":"hvac.bedroom_1","anchor_step_id":"recovery-knot-1-hvac.bedroom_1","anchor_target_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","controlled_channel":"hvac_state","divergent_facets":["setpoint_c"],"event":"activated","expectation_activation_ids":{"setpoint_c":"activation-12"},"expectation_generation_ids":{"setpoint_c":"gen-4"},"expectation_reaction_ids":{"setpoint_c":"comfort_trajectory_bedroom"},"expectation_step_ids":{"setpoint_c":"recovery-knot-1-hvac.bedroom_1"},"expectation_target_fingerprints":{"setpoint_c":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"expected_fingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","expected_values":{"setpoint_c":"21.5"},"expires_at":null,"hold_id":"hold-hvac-01","invalidation_reason":null,"observation_context":"normal","observed_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","observed_values":{"setpoint_c":"19"},"operation_id":"c02f7a3f6680fc2d9acfd103fb6de98e05520858ce33e6e02bbe90f9f4184b3b","origin":"resident_manual","origin_evidence":"direct_authenticated_command","reaction_activation_id":"activation-12","reaction_generation_id":"gen-4","reaction_id":"comfort_trajectory_bedroom","release_mode":"next_reaction_step","release_reason":null,"scope":"channel"}
```

Persisted `ReactionFollowUpIntent`:

```json
{"actuator_id":"hvac.bedroom_1","configuration_generation_id":"gen-4","controlled_channel":"hvac_state","expected_facets":{"mode":"\"heating\"","setpoint_c":"21.5"},"hold_id":"hold-hvac-01","later_step_remains":false,"observation_available":true,"observation_epoch_id":"epoch-9","observed_at":"2026-10-03T20:00:00.000000+00:00","observed_facets":{"mode":"\"heating\"","setpoint_c":"19"},"operation_id":"739c1c9f27316249ad18a02f6fb08f85a1f2a860596642506c9022fc56ad7989","path":"normal_exit","planned_step_id":null,"prepared_at":"2026-10-03T20:00:01.000000+00:00","reaction_activation_id":"activation-12","reaction_descriptor_id":"environment.planned_comfort_trajectory","reaction_id":"comfort_trajectory_bedroom","subject":"[\"room\",\"bedroom\"]"}
```

`OperationalEventValue` for `reaction.follow_up`:

```json
{"context":{"actuator_id":"hvac.bedroom_1","configuration_generation_id":"gen-4","controlled_channel":"hvac_state","expected.mode":"\"heating\"","expected.setpoint_c":"21.5","hold_id":"hold-hvac-01","later_step_remains":false,"observation_available":true,"observation_epoch_id":"epoch-9","observed.mode":"\"heating\"","observed.setpoint_c":"19","observed_at":"2026-10-03T20:00:00.000000+00:00","operation_id":"739c1c9f27316249ad18a02f6fb08f85a1f2a860596642506c9022fc56ad7989","outcome":"ended_without_final_target","path":"normal_exit","planned_step_id":null,"reaction_activation_id":"activation-12","reaction_descriptor_id":"environment.planned_comfort_trajectory","reaction_id":"comfort_trajectory_bedroom"},"context_version":1,"notification_key":"reaction.follow_up:739c1c9f27316249ad18a02f6fb08f85a1f2a860596642506c9022fc56ad7989","severity":"warning"}
```
