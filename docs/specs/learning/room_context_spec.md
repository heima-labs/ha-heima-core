# Room Context Model

## Scope

Room context is a preprocessing layer for v2 inference. It is not a DAG domain and it does not scan
Home Assistant inventory. It derives per-room device context from entities the user already
configured in Heima options, using HA area assignments only to map those configured entities back to
Heima rooms.

## Contract

`RoomDeviceContext` is the canonical per-room vector:

- `room_id`
- `media_on`
- `lights_on`
- `work_activity`
- `pc_active`

`occupied` is intentionally excluded because room occupancy already exists in `room_occupancy`.

## Entity Mapping

`RoomDeviceContextBuilder` reads configured entities only:

- `house_state_config.media_active_entities`
- `house_state_config.work_activity_entities`
- `activity_bindings.pc_active`
- current `lights_physically_on` entity ids

For each configured entity it resolves HA area with the same pattern used by `room_inventory.py`:

1. entity registry `entry.area_id`
2. device registry fallback via `entry.device_id -> device.area_id`
3. reverse lookup against `options["rooms"][*]["area_id"]`

Entities without a matching HA area do not enter `RoomDeviceContext`; they continue to contribute
only through existing global aggregates.

The coordinator subscribes to `EVENT_ENTITY_REGISTRY_UPDATED` and `EVENT_AREA_REGISTRY_UPDATED`.
Registry changes mark the mapping stale; the next runtime cycle rebuilds it.

## Runtime Flow

The engine computes room context after occupancy and before inference signal collection / house state
resolution. It writes the serialized mapping to `CanonicalState["rooms.device_context"]`, passes the
typed mapping in `InferenceContext.room_device_context`, and persists it in
`HouseSnapshot.room_device_context`.

After Lighting runs, the engine recomputes the context with current physical light states so persisted
snapshots carry current `lights_on` data. House-state resolution only depends on media/work/pc fields.

## House State Resolver

When room context is available for occupied rooms:

- relax media evidence is `media_on=True AND work_activity=False AND pc_active=False` in the same
  occupied room
- media in a room with work activity does not create relax evidence
- work activity can be satisfied by `work_activity=True` or `pc_active=True` in an occupied room

If there is no room context for occupied rooms, resolver behavior falls back to the existing global
aggregates.

## Learning Module

`RoomContextModule` learns approved house-state signals from:

`P(house_state | weekday, hour_bucket, room_context_pattern)`

where:

`room_context_pattern = frozenset((room_id, media_on, work_activity) for occupied rooms)`

`lights_on` and `pc_active` are excluded from the pattern key because they are noisier
discriminants. Historical snapshots without `room_device_context` are ignored by this module.

The module uses the existing house-state learned-context approval flow. Its approval key includes
`learning_context.module = "room_context"` and the canonical room-context pattern, so it does not
collide with `HouseStateInferenceModule`.

## Extensibility Direction

Room context should become easier to extend, but Phase X intentionally does not expose a public plugin
API. The current contract is still settling in several places:

- `HouseStateDomain` reads explicit `RoomDeviceContext` attributes
- `RoomContextModule` has a deliberately small hardcoded learning key
- `HouseSnapshot.room_device_context` is persisted as schema-light dict data
- approval keys include room-context pattern data and must remain stable once approved

Publishing a third-party API before those contracts settle would force backward compatibility on
signal names, value types, aggregation rules, snapshot migrations, and approval-key hashing too early.

The intended next step is an internal provider interface, not a public extension API:

```python
class RoomContextSignalProvider(Protocol):
    signal_name: str

    def configured_entities(self, options: dict[str, Any]) -> list[str]:
        ...

    def compute_entity_value(
        self,
        *,
        entity_id: str,
        hass: HomeAssistant,
        normalizer: InputNormalizer,
        options: dict[str, Any],
    ) -> bool | str | float | None:
        ...

    def default_value(self) -> bool | str | float | None:
        ...
```

The builder remains the only owner of entity-to-room mapping. Providers declare configured entities
and compute canonical values; they must not perform their own HA area/device lookup.

The current `RoomDeviceContext` dataclass should remain as a compatibility layer for the core fields:

- `media_on`
- `lights_on`
- `work_activity`
- `pc_active`

Future internal providers can add signals first through an `extra_signals`-style extension, while the
core dataclass fields keep existing resolver and learning behavior stable. Only after several real
signals exist should the model move to a fully generic structure such as
`signals: dict[str, CanonicalRoomSignal]`.

Candidate next signals:

- `screen_active`
- `audio_active`
- `desk_activity` / `workstation_active`
- `appliance_active`
- `environment_activity`

New signals must also declare intended consumers separately: house-state resolver, room-context
learning key, activity inference, anomaly detection, or diagnostics. Adding a signal must not
automatically place it in the learning key.
