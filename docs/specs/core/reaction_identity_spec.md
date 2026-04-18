# Reaction Identity Spec
## `reaction_type` as canonical reaction key

**Status**: Active v1.x reaction identity contract
**Last Verified Against Code**: 2026-04-18

---

## Problema

Attualmente ogni entry in `options.reactions.configured` contiene due campi identitari:

| Campo | Esempio | Layer |
|---|---|---|
| `reaction_type` | `"room_darkness_lighting_assist"` | Proposta / learning |
| `reaction_class` | `"RoomLightingAssistReaction"` | Plugin registry / runtime |

Questo produce:
- Dual-path check ovunque (`reaction_type == "X" or reaction_class == "Y"`)
- Ambiguità su quale campo usare in nuovi punti di codice
- `reaction_class` esposto in diagnostics/UI come se fosse un contratto pubblico
- Debug tooling locale che deve indovinare quale dei due campi sia davvero valorizzato
- Più rischio di mismatch fra:
  - config flow
  - rebuild runtime
  - diagnostics
  - script di debug

---

## Soluzione

`reaction_type` diventa l'**unico identificatore persistito** nelle options.
`reaction_class` diventa un dettaglio interno del registry, non salvato in `configured`.

### Invarianti post-riforma

1. `options.reactions.configured[id]["reaction_type"]` è sempre presente e non vuoto.
2. `reaction_class` non appare mai in `configured` per entry nuove.
3. Il registry mappa `reaction_type → builder` (non `reaction_class → builder`).
4. Tutto il dispatch (engine, config_flow, diagnostics) usa `reaction_type`.
5. Le reaction admin-authored e learned condividono lo stesso formato persistito in `configured`.
6. `reaction_class` può ancora esistere in memoria nel registry o nel codice Python, ma non è più un campo contrattuale di persistenza.

---

## Caso N:1 — più tipi, stessa implementazione

Tre `reaction_type` condividono oggi la stessa classe Python:

| `reaction_type` | `reaction_class` (interno) |
|---|---|
| `room_signal_assist` | `RoomSignalAssistReaction` |
| `room_cooling_assist` | `RoomSignalAssistReaction` |
| `room_air_quality_assist` | `RoomSignalAssistReaction` |

Post-riforma il registry ha entry esplicite per tutti e tre i tipi, ognuna con il proprio builder. I builder possono condividere la stessa implementazione Python ma il lookup avviene per `reaction_type`.

---

## Modifiche per layer

### 1. `runtime/reactions/__init__.py` — ReactionPluginRegistry

**Prima**: keyed by `reaction_class`
**Dopo**: keyed by `reaction_type`

```python
# Descrittore del plugin
@dataclass
class ReactionPluginDescriptor:
    reaction_type: str        # chiave canonica (es. "room_signal_assist")
    reaction_class: str       # nome Python interno, usato solo per log/debug
    ...

# Registry lookup
def builder_for(self, reaction_type: str) -> ReactionPluginBuilder | None: ...
def presenter_for(self, reaction_type: str) -> ReactionPresenterHooks | None: ...
```

Entry esplicite per i tre tipi N:1:
```python
RegisteredReactionPlugin(descriptor=ReactionPluginDescriptor(
    reaction_type="room_signal_assist",
    reaction_class="RoomSignalAssistReaction",
    ...
), builder=_build_room_signal_assist)

RegisteredReactionPlugin(descriptor=ReactionPluginDescriptor(
    reaction_type="room_cooling_assist",
    reaction_class="RoomSignalAssistReaction",  # stesso builder
    ...
), builder=_build_room_signal_assist)

RegisteredReactionPlugin(descriptor=ReactionPluginDescriptor(
    reaction_type="room_air_quality_assist",
    reaction_class="RoomSignalAssistReaction",  # stesso builder
    ...
), builder=_build_room_signal_assist)
```

### 2. `runtime/engine.py`

- `_rebuild_configured_reactions`: lookup via `cfg["reaction_type"]` invece di `cfg["reaction_class"]`
- `_configured_reaction_ids_by_type`: già usa `reaction_type`, nessun cambiamento
- `mute/unmute_reactions_by_type`: nessun cambiamento
- `heima_reactions_active` e diagnostics runtime espongono `reaction_type` come chiave semantica primaria

### 3. `config_flow/_steps_reactions.py`

- Dispatch del form di edit: da `reaction_class` a `reaction_type`
- `_configured_reaction_from_proposal`: rimuove `reaction_class` dal dict salvato
- Tutti i dual-path check eliminati: solo `reaction_type`
- I path admin-authored diretti in `options.reactions.configured` scrivono sempre `reaction_type`
- Presenter labels e gruppi UI usano `reaction_type` come discriminante canonico

### 4. `runtime/proposal_engine.py`

- Già usa `reaction_type` come campo primario. Rimuovere `reaction_class` dal dict serializzato delle proposal.

### 5. `diagnostics.py`

- Tutti i dual-path check → solo `reaction_type`
- Display e raggruppamento già funzionano su `reaction_type`

### 6. `debug/` scripts locali

- Tutti i filtri locali su reaction family usano `reaction_type`
- Se il payload live è legacy, gli script possono fare fallback temporaneo `reaction_class -> reaction_type`
- Il fallback resta confinato al compat layer e viene rimosso dopo la migration repo-wide

---

## Migration — dati esistenti

Le entry in `configured` già presenti nell'installazione live hanno `reaction_class` ma potrebbero mancare di `reaction_type` (o averlo entrambi).

**Strategia**: migration one-shot al primo load post-deploy.

Mapper backward-compat (interno, usato solo durante la migration):

```python
_CLASS_TO_TYPE: dict[str, str] = {
    "LightingScheduleReaction": "lighting_scene_schedule",
    "RoomSignalAssistReaction": "room_signal_assist",   # default per i tre N:1
    "RoomLightingAssistReaction": "room_darkness_lighting_assist",
    "RoomLightingVacancyOffReaction": "room_vacancy_lighting_off",
    "VacationPresenceSimulationReaction": "vacation_presence_simulation",
    "HeatingPreferenceReaction": "heating_preference",
    "HeatingEcoReaction": "heating_eco",
    "PresencePatternReaction": "presence_preheat",
}
```

**Nota**: per `RoomSignalAssistReaction` il mapper produce `room_signal_assist` di default — `room_cooling_assist` e `room_air_quality_assist` vengono prodotti solo da nuove entry post-riforma. Le entry migrate funzionano correttamente perché `room_signal_assist` è il tipo generico.

La migration avviene in `async_reload_options` (o in un helper chiamato da lì) e riscrive `options` se trova entry con `reaction_class` ma senza `reaction_type`.

### Regole della migration

1. Se `reaction_type` è presente e non vuoto:
   - resta la source of truth
   - `reaction_class` legacy viene rimosso dal payload persistito
2. Se `reaction_type` manca ma `reaction_class` è noto:
   - viene popolato via mapper
   - poi `reaction_class` viene rimosso
3. Se mancano entrambi:
   - la reaction viene lasciata intatta
   - viene emesso warning
   - il rebuild runtime la ignora
4. Se i due campi esistono ma sono incoerenti:
   - prevale `reaction_type`
   - `reaction_class` viene scartato

---

## Cosa scompare

| Elemento | Stato post-riforma |
|---|---|
| `configured[id]["reaction_class"]` | Rimosso dalle nuove entry; migration lo rimuove dalle vecchie |
| `ReactionPluginRegistry.builder_for(reaction_class)` | Firma cambia in `builder_for(reaction_type)` |
| Dual-path `or` check | Eliminati |
| `reaction_class` in diagnostics output | Rimosso o spostato in sezione debug-only |

---

## Cosa rimane invariato

- `reaction_type` in `ReactionProposal` (già corretto)
- `mute_reaction_type` / `unmute_reaction_type` service (già usano `reaction_type`)
- Lifecycle hooks keyed by `reaction_type` in `LearningPluginRegistry`
- Identity key / deduplication logic (già usa `reaction_type`)

---

## Rischi

| Rischio | Mitigazione |
|---|---|
| Migration fallisce su entry malformate (né `reaction_type` né `reaction_class`) | Entry skippata con log warning; reazione non attiva ma options non corrotte |
| N:1 mapping produce tipo sbagliato per entry migrate | Accettabile: `room_signal_assist` copre il caso generale; le varianti `cooling`/`air_quality` sono generate solo da nuovi proposal |
| Test che cercano `reaction_class` in `configured` | Da aggiornare nella stessa PR |

---

## Scope della PR

1. `runtime/reactions/__init__.py` — registry keyed by `reaction_type`, entry esplicite N:1
2. `runtime/engine.py` — lookup su `reaction_type`
3. `config_flow/_steps_reactions.py` — dispatch e storage
4. `runtime/proposal_engine.py` — rimozione `reaction_class` dal serializzato
5. `diagnostics.py` — eliminazione dual-path
6. Migration helper in `async_reload_options`
7. Tooling locale `debug/` — filtri e presenter allineati a `reaction_type`
8. Test: aggiornare tutti i check su `reaction_class` in `configured`

---

## Acceptance Criteria

- Una reaction nuova salvata in `options.reactions.configured` contiene `reaction_type` ma non `reaction_class`
- `_rebuild_configured_reactions()` riesce a ricostruire tutte le reaction supportate usando solo `reaction_type`
- Il config flow `Modifica reazione` dispatcha correttamente senza leggere `reaction_class`
- `diagnostics --section reactions` non dipende da `reaction_class`
- Gli script di debug stanza/reaction mostrano le reaction corrette anche dopo la rimozione di `reaction_class`
- La migration converte correttamente le entry legacy più comuni senza corrompere le options

Nessuna modifica alle API pubbliche (services, eventi HA).
