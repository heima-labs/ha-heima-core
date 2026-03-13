# Heima - Piano di Sviluppo (v1.x)

## Sintesi
Heima e una integrazione custom per Home Assistant che fornisce un motore di policy per casa intelligente. L'integrazione crea e possiede entita canoniche, calcola stato della casa e intenti, e applica azioni in modo sicuro tramite un orchestratore. L'architettura e intent-driven e supporta un framework di behavior estendibile senza fork del core.

## Obiettivi v1
- Integrare i domini core: people, occupancy, house_state, lighting, heating, security (read-only), notifications.
- Implementare Options Flow completo con validazione forte e salvataggio in config entry.
- Creare tutte le entita canoniche con unique_id stabili.
- Eseguire policy e applicazioni tramite orchestratore con sicurezza, dedup, rate limit.
- Esporre eventi e servizi pubblici secondo la strategia di estensione (Solution A).

## Presupposti
- Home Assistant fornisce UI, storage, servizi, eventi e registry entita.
- Heima non controlla device direttamente, ma solo tramite scene e climate service.
- Le specifiche v1 e v1.1 sono contratti stabili per v1.x.

## Principio architetturale core: DAG di domini con memoria inter-ciclo

I domain handler formano un DAG (Direct Acyclic Graph, Grafo Aciclico Orientato) per ciclo di valutazione. Ogni handler:
- puo leggere `CanonicalState` (risultato del ciclo precedente) come input
- NON puo leggere l'output del ciclo corrente di un altro handler
- riceve in input i risultati degli handler che precedono nel DAG del ciclo corrente

`CanonicalState` e sia storage per le entity HA sia memoria condivisa tra cicli:
il valore canonico di ogni dominio al termine di un ciclo diventa input disponibile
per tutti i domini nel ciclo successivo.

Questo consente a `house_state` di essere un layer di inferenza convergente: piu segnali
osserva (presenza, occupancy, stato lighting, fase heating, tempo), meno richiede
configurazione esplicita da parte dell'utente. L'obiettivo a lungo termine e che
`house_state` venga inferito automaticamente dai pattern comportamentali della casa,
non impostato tramite helper entity.

Ordine di valutazione nel ciclo (DAG):
1. Normalizzazione osservazioni (InputNormalizer - nessuna dipendenza)
2. People + Anonymous presence (legge osservazioni normalizzate)
3. Occupancy per room (legge osservazioni normalizzate)
4. house_state inference (legge osservazioni + CanonicalState + people + occupancy)
5. Domain intents: lighting, heating, security (leggono house_state + CanonicalState)
6. Apply plan + apply
7. Aggiornamento CanonicalState (diventa input del prossimo ciclo)

## Milestone
1. Milestone 0 - Scaffolding e Contratto Entita
2. Milestone 1 - MVP Portabile
3. Milestone 2 - Heating Safe Engine
4. Milestone 1.1 - Behavior Framework v1

## Stato Milestone (aggiornato)
- Milestone 0: raggiunta.
- Milestone 1: sostanzialmente raggiunta per il perimetro MVP portabile (people, anonymous, occupancy, house_state, lighting, notification pipeline base, diagnostica principale).
- Milestone 2: sostanzialmente raggiunta come Heating MVP sicuro (branch per `house_state`, safe apply, vacation curve, scheduler condiviso, osservabilita, test). Restano rifiniture e validazione manuale finale.
- Milestone 1.1: infrastruttura base completata (HeimaBehavior, dispatch, constraints layer v0.3.0). Behavior concreti con apply_filter rimandati — apply_filter su behavior e ridondante con il constraints layer senza tags su ApplyStep; l'use case primario per i behavior e l'observability passiva (on_snapshot).
- Cross-cut Normalization Layer: rollout avanzato e gia integrato nei path runtime principali; il framework e ormai oltre lo stato sperimentale.
- Cross-cut Policy Plugin Framework: definito a livello spec, non ancora implementato nel runtime.

## Milestone 0 - Scaffolding e Contratto Entita
- Inizializzare struttura integrazione.
- Creare manifest, const, setup/unload entry, logger e diagnostics stub.
- Definire registry delle entita canoniche.
- Definire modelli dati per config entry e runtime state.

Output:
- Integrazione caricabile.
- Entita canoniche registrate senza logica di policy.

## Milestone 1 - MVP Portabile
- People adapter.
- Anonymous presence.
- Occupancy per room e zone.
- House state deterministico.
- Lighting intent per zone e apply per room con hold.
- Notification pipeline base con event catalog e rate limit.
- Hardening UX/config flow per modifiche opzioni e diagnostica lighting.

Output:
- Ciclo completo di evaluation e apply per lighting.
- Eventi standard emessi via bus HA.
- Tracciabilita diagnostica di decisioni lighting (zone/room trace).

## Milestone 2 - Heating Safe Engine
- Intenti heating e selettore canonico.
- Orchestratore heating con rate limit, guard, verify e retry.
- Rilevamento override manuale e notifiche.

Output:
- Heating applicato in modo sicuro e idempotente.

## Milestone 1.1 - Behavior Framework v1
- Registro behaviors built-in.
- Hook points: on_snapshot, lighting_policy, apply_filter.
- Risoluzione conflitti hard/soft con priorita.
- Behavior lighting.time_windows.

Output:
- Behavior configurabili via Options Flow.
- Policy lighting estendibile.

## Stream di Lavoro
### 1. Config Flow e Options Flow
- Implementare flusso opzioni completo secondo spec.
- Validazioni su entity_id, slug univoci, quorum.
- Migrazioni config entry v1.x.
- Stato attuale:
  - implementato e funzionante
  - corretti bug di persistenza/edit form
  - corretta gestione campi selector opzionali clearabili
  - aggiunto supporto room `occupancy_mode = none`

### 2. Entita Canoniche
- Generazione entita per persone, occupancy, house_state.
- Entita lighting e heating intents.
- Entita security e notification.

### 3. Snapshot e Decision Engine
- Snapshot canonico con stato persone, occupancy e house_state.
- Decision engine per intent lighting e heating.
- Debug notes e diagnostica di snapshot.
- Stato attuale:
  - people/anonymous/occupancy/house_state implementati
  - lighting intent/apply v1 implementato
  - room senza sensori (`occupancy_mode = none`) supportate
  - zone occupancy calcolata ignorando room non sensorizzate
  - input normalization layer plugin-first introdotto e usato nei path principali (occupancy, people quorum, house signals, security)
  - house-state signal bindings (`vacation`, `guest`, `sleep`, `relax`, `work`) are configurable in the Options Flow instead of relying on hardcoded helper entity ids
  - occupancy plugin-first con dwell/max_on operativo e `weighted_quorum` disponibile
  - plugin layer esteso oltre la presenza:
    - corroborazione security (`boolean_signal`)
    - composizione house helper (`boolean_signal`)
  - contratti riusabili di strategia (`SignalSetStrategyContract`) introdotti per:
    - group presence
    - room occupancy
    - security corroboration
    - house signals
  - Heating MVP implementato:
    - branch built-in per `house_state`
    - `fixed_target`
    - `vacation_curve`
    - `heima.set_mode` come final house-state override

### 4. Orchestratore e Apply
- Orchestratore unico per apply.
- Decomposizione zone -> room (scene.turn_on).
- Anti-loop, dedup e idempotenza per scene.
- Hold per room e manual override per heating.
- Stato attuale:
  - apply lighting integrato nel runtime engine (scene + fallback `light.turn_off(area)`)
  - idempotenza/rate-limit per room implementati
  - diagnostica conflitti room-in-piu-zone presente
  - apply Heating integrato nel runtime engine (`climate.set_temperature`) con guard e rate-limit
  - orchestratore separato non ancora estratto

### 5. Notification Pipeline
- Implementare event envelope.
- Dedup e rate limit per key.
- Routing su notify.* configurati.
- Stato attuale:
  - implementato (bus `heima_event` + routing `notify.*`)
  - supporta destinatari logici (`recipients` / `recipient_groups`) risolti in `notify.*`
  - `notifications.routes` deprecato e chiuso lato runtime: delivery solo su target logici
  - bridge automatico in Options Flow per profili `routes`-only (`legacy_routes` -> `recipients` + `route_targets`)
  - `notifications.routes` rimosso dalla UI Notifications (rimane solo input legacy di migrazione in normalize)
  - warning runtime `system.notifications_routes_deprecated` mantenuto per cleanup guidato
  - `heima.command notify_event` integrato nel pipeline unificato
  - sensori `heima_last_event` / `heima_event_stats` aggiornati
  - catalogo v1 allineato ai nomi/event payload runtime; `heating.verify_failed` / `heating.apply_failed` mantenuti deferred esplicitamente
  - `security.mismatch` introdotto come evento canonico con compat mode (`explicit_only|generic_only|dual_emit`)

### 6. Estensioni (Solution A)
- Eventi: heima_event, heima_snapshot (opzionale), heima_health (opzionale).
- Servizi: heima.command, heima.set_mode, heima.set_override.
- Validazione comandi e errori chiari.
- Stato attuale:
  - `heima.command` operativo per i comandi implementati
  - `heima.set_mode` operativo come override finale runtime-only del `house_state`
  - `heima.set_override` operativo per gli override gia supportati

### 7. Diagnostica e Privacy
- Diagnostica include mapping, last applied, eventi recenti.
- Redazione di dati sensibili.
- Stato attuale:
  - diagnostics globali del normalizer (`registered_plugins`, error counters, last fallback/error)
  - trace locali nei punti runtime rilevanti:
    - `presence.group_trace`
    - `occupancy.room_trace`
    - `security.observation_trace`
    - `security.corroboration_trace`
    - `house_signals.trace`
    - `house_state_override`
    - `runtime.scheduler`

### 8. Localizzazione
- Traduzioni base en/it per labels e errori.

### 9. Heating Domain (implementation track)
- H4.1 Domain Foundation
  - bind `climate_entity`
  - creare entita canoniche heating reali
  - aggiungere diagnostica base heating
  - introdurre il config model base:
    - `apply_mode`
    - `temperature_step`
    - `manual_override_guard`
    - `override_branches`
- H4.2 Safe Apply Path
  - leggere setpoint corrente
  - guard `small_delta`
  - rate limit / idempotenza
  - manual override guard
  - prime emissioni `heating.apply_skipped_small_delta` / `heating.manual_override_blocked`
- H4.3 Vacation Timing Bindings
  - collegare sensori/helper per:
    - `hours_from_start`
    - `hours_to_end`
    - `total_hours`
    - `is_long`
    - `outdoor_temperature`
  - modellare i relativi binding espliciti nel config heating
- H4.4 Vacation Curve Policy Branch
  - introdurre il branch selector per `house_state`
  - supportare catalogo built-in:
    - `scheduler_delegate`
    - `fixed_target`
    - `vacation_curve`
  - implementare `vacation_curve` con `eco_only`, `ramp_down`, `cruise`, `ramp_up`
  - safety floor da temperatura esterna
  - quantizzazione sul passo termostato
- H4.5 Normal Branch Semantics
  - rendere esplicito il comportamento scheduler-following fuori da `vacation`
- H4.6 Events and Observability
  - introdurre eventi heating iniziali e trace diagnostico strutturato
- H4.7 Automated Tests
  - unit test policy curve
  - runtime test branch/apply guard
  - HA e2e test con `ConfigEntry`
- Stato attuale:
  - implementato come Heating MVP
  - `scheduler_delegate`, `fixed_target`, `vacation_curve`
  - safe apply con:
    - manual hold
    - thermostat preset manual-override detection
    - small-delta skip
    - rate limit / idempotenza
  - scheduler condiviso usato per timed rechecks del `vacation_curve`
  - eventi:
    - `heating.vacation_phase_changed`
    - `heating.target_changed`
    - `heating.branch_changed`
    - `heating.apply_skipped_small_delta`
    - `heating.manual_override_blocked`
    - `heating.apply_rate_limited`
    - `heating.vacation_bindings_unavailable`
- Future enhancement:
  - `heating.apply_drift_detected`: emettere se dopo N cicli il setpoint letto da HA differisce ancora dal target di piu di `temperature_step`, segnalando che il cloud o il device non ha recepito il comando. La verifica e naturale (next-cycle read-back da CanonicalState), nessun verify esplicito necessario.

### 10. Policy Plugin Framework (future track)
- P0 Spec Foundation
  - mini-spec cross-domain definita
  - separazione esplicita da normalization plugins
  - Heating identificato come primo adopter futuro
- P1 Framework Only
  - introdurre registry policy plugin
  - dispatcher per hook `pre_policy`, `domain_policy`, `post_policy`, `apply_filter`
  - diagnostica e gestione errori/fallback
- P2 First Real Adoption
  - migrare Heating `vacation_curve` da branch fisso a primo built-in policy plugin, senza cambiare comportamento
- P3 Domain Expansion
  - estendere con cautela a Lighting / Watering / Constraints dopo stabilizzazione Heating

## Modello Dati (Sintesi)
- People: binary_sensor, sensor confidence, source, override.
- Anonymous presence: binary_sensor, confidence, source.
- Occupancy: binary_sensor per room e zone.
- House state: sensor state + reason.
- Lighting: select intent per zone, hold per room.
- Heating: select intent, hold, applying_guard.
- Security: select intent, state, reason.
- Notification: last_event, event_stats.

## Testing e Qualita
- Test unit per decision logic e mapping fallback.
- Test integration per Options Flow e servizi.
- Test di idempotenza apply.
- Validazione rate limit e dedup eventi.
- Stato attuale:
  - test unit + runtime + servizi + flow-style tests presenti
  - aggiunto harness HA reale (`pytest-homeassistant-custom-component`)
  - presenti test end-to-end con `ConfigEntry` e setup integrazione per:
    - room occupancy dwell
    - `weighted_quorum`
    - people quorum
    - anonymous presence
    - fail-safe fallback path
    - security corroboration trace
    - house helper signal trace
  - coperti regression bug principali (selector clear, lighting conflicts, notify pipeline)
  - aggiunti test HA e2e per Heating e scheduler runtime
  - suite locale: `120 passed`

## Rischi e Mitigazioni
- Config incoerente: validazioni strette + eventi system.config_invalid.
- Loop di apply: anti-loop per room e guard heating.
- Privacy: redazione contesto eventi e snapshot opzionale.

## Prossimi Passi Operativi
1. Completare Phase 7 (Reactive Behavior Engine) per step incrementali secondo le priorita definite nella sezione dedicata.
2. Validazione manuale Heating in HA reale: vacation curve progression, branch editing, set_mode.
3. Rafforzare lighting con policy conflitti zone-room configurabile (first_wins/priority).
4. Policy Plugin Framework (P1) rimane track separato, da valutare dopo stabilizzazione Phase 7 R2.

---

## Phase 7: Reactive Behavior Engine

### Visione

Heima osserva pattern comportamentali nel tempo tramite una sliding window di snapshot
e reagisce autonomamente producendo ApplyStep aggiuntivi che vanno ad arricchire il piano
di applici senza sostituire la logica di dominio esistente.

La logica di riconoscimento pattern (IPatternDetector) e quella di adattamento/apprendimento
(ILearningBackend) sono pluggabili: si parte da regole deterministiche semplici e si
possono aggiungere backend statistici o ML senza toccare il core engine.

I passi prodotti dalle reazioni passano attraverso il constraint layer esistente — stessa
pipeline, stesse garanzie di sicurezza.

### Relazione con framework Behavior esistente

- `HeimaBehavior` (v0.3.0, esistente): observer passivo — `on_snapshot` per diagnostics/history.
  Rimane per observability. `apply_filter` disponibile come extension point avanzato
  ma non raccomandato senza tags su ApplyStep.
- `HeimaReaction` (Phase 7, nuovo): contributor attivo — `evaluate(history) -> list[ApplyStep]`.
  Non filtra, non blocca: aggiunge passi al piano basandosi su pattern temporali.

### Concetti Fondamentali

**`SnapshotBuffer`** — ring buffer bounded di N DecisionSnapshot (default 20) mantenuto
dall'engine dopo ogni ciclo di valutazione. Esposto come `engine.snapshot_history`.

**`HeimaReaction`** — componente che osserva la history e produce ApplyStep:
```python
class HeimaReaction:
    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]: ...
    def on_options_reloaded(self, options: dict) -> None: ...
    def diagnostics(self) -> dict: ...
```

**`IPatternDetector`** — plugin stateless che valuta una condizione sulla history:
```python
class IPatternDetector(Protocol):
    def matches(self, history: list[DecisionSnapshot]) -> bool: ...
```

**`ILearningBackend`** — plugin per adattamento/confidenza:
```python
class ILearningBackend(Protocol):
    def observe(self, reaction_id: str, fired: bool, steps: list[ApplyStep]) -> None: ...
    def confidence(self, reaction_id: str) -> float: ...  # 0.0–1.0
```
Se `confidence < threshold` (default 0.5), la reaction viene silenziata e loggata.

### Principi di Design

- **Stabilita prima di tutto**: ogni step e autonomo, non rompe il runtime esistente.
- **Plugin-first**: IPatternDetector e ILearningBackend sono sostituibili liberamente.
- **Constraint layer invariante**: tutti gli step (domain + reaction) passano dal constraint layer.
- **Learning solo opt-in**: ILearningBackend attivato solo se configurato esplicitamente.
- **Reversibilita**: reaction silenziabili a runtime tramite `heima.command`.
- **No refactor pesanti**: il piano usa ApplyStep gia esistente; nessuna modifica ai domain handler.

### Step R0 — SnapshotBuffer (prerequisito per tutto)

- Ring buffer di N snapshot (default 20) mantenuto da engine dopo ogni `async_evaluate`.
- API: `engine.snapshot_history: list[DecisionSnapshot]` (piu recente ultimo).
- Test unitari del buffer (bounds, ordering, thread-safety non necessaria — loop asincrono).
- **Dipendenze**: nessuna. Implementabile senza toccare domain logic.

### Step R1 — HeimaReaction base + integrazione engine

- `HeimaReaction` base class in `runtime/reactions/base.py`.
- `register_reaction(reaction)` in engine (separato da `register_behavior`).
- Dispatch dopo `_build_apply_plan`:
  `reaction_steps = _dispatch_reactions(history)` → merge nel piano come step con tag `source=reaction:{id}`.
- Tag `source` aggiunto ad `ApplyStep` come campo opzionale (stringa vuota default) — unica modifica a contracts.py.
- Constraint layer si applica normalmente ai reaction_steps.
- Test base: dispatch, exception isolation, diagnostics.

### Step R2 — IPatternDetector + ConsecutiveStateReaction (prima reazione built-in)

- `ConsecutiveStateReaction`: si attiva quando `predicate(snapshot) == True` per N snapshot consecutivi.
- Config: `predicate` (callable), `consecutive_n: int`, `step_template: ApplyStep`.
- Casi d'uso immediati:
  - `house_state == 'away'` per 3+ cicli → eco heating step
  - `anyone_home == False` per 5+ cicli → turn-off lighting in zone non presidiate
- Test: predicate matching, threshold N, reset counter se condition cade.
- **Da qui la suite e gia utile in produzione.**

### Step R3 — ILearningBackend + NaiveLearningBackend

- Interfaccia `ILearningBackend` in `runtime/reactions/learning.py`.
- `NaiveLearningBackend`:
  - Conta override utente post-reaction (rilevato da: step prodotto da reaction, poi snapshot successivo con stato inverso non generato da heima).
  - Abbassa confidence dopo K override consecutivi (default K=3, configurable).
  - Reset confidence su N cicli senza override (default N=20).
- `confidence < 0.5` → reaction silenziata, evento `reaction.suppressed` emesso.
- Pluggabile: future `StatisticalBackend`, `MLBackend` implementano stessa interfaccia.
- Test: counter increment, confidence decay, reset, suppression event.

### Step R4 — PresencePatternReaction (prima reazione adattiva)

- Apprende le fasce orarie tipiche di arrivo per le persone configurate.
- Pattern: "persona X torna nei giorni feriali nella finestra 17:30–18:30".
- Trigger: N minuti prima della finestra attesa → emette step di pre-conditioning
  (es. heating setpoint +1°C, lighting zona ingresso al 30%).
- Usa `NaiveLearningBackend`: se l'utente abbassa subito la temperatura/luce, confidence scende.
- La finestra si apprende accumulando snapshot con `anyone_home` che passa False→True per orario.
- Test: learning accumulation, trigger timing, confidence feedback.

### Step R5 — Config, Observability, Commands

- Reaction config leggibile da Options Flow (abilita/disabilita singola reaction, parametri soglia, backend).
- Sensor canonico `heima_reactions_active`: JSON con lista reazioni attive, confidence, last_fired.
- Evento `reaction.fired` nel pipeline notifiche (con context: reaction_id, steps_count, confidence).
- Diagnostics per reaction: `last_fired_ts`, `confidence`, `override_count`, `suppressed_count`.
- Comando `heima.command` con `command: mute_reaction` / `unmute_reaction`.

### Stato

- R0: completato — SnapshotBuffer, 13 test
- R1: completato — HeimaReaction base, engine dispatch, source tag su ApplyStep, 14 test
- R2: completato — IPatternDetector, ConsecutiveMatchDetector, ConsecutiveStateReaction, 22 test
- R3: completato — ILearningBackend, NaiveLearningBackend, integrazione ConsecutiveStateReaction, 22 test
- R4: completato — PresencePatternReaction (learn + trigger + midnight wrap), 28 test
- R5: completato — heima_reactions_active sensor, reaction.fired event, mute_reaction/unmute_reaction commands, 15 test (Options Flow escluso per v1)

---

## Phase CF — Config Flow Refactor

Branch: `feature/config-flow-refactor`

### Problema attuale

Il config flow (1562 righe, file monolitico) è un wizard lineare obbligatorio:
`general → people → rooms → lighting rooms → lighting zones → heating → security → notifications`

Problemi:
- Navigazione rigida: per modificare le notifiche bisogna passare per tutti gli step
- Nessuna sezione Reactions
- `general` mescola concetti distinti (sistema, lighting mode, house signals)
- Codice non suddiviso: difficile manutenere e testare step singoli

### Obiettivo

1. **Menu toplevel** (`async_show_menu`): ogni sezione è accessibile direttamente
2. **Package split**: `config_flow/` con un modulo per sezione
3. **Sezione Reactions**: catalog built-in, enable/disable, parametri per-reaction
4. **Mute persistito**: stato muted salvato in config entry (sopravvive al restart)

---

### Step CF1 — Package split (behavior-preserving)

**Obiettivo**: zero cambiamenti funzionali, solo ristrutturazione.

Struttura target:
```
custom_components/heima/config_flow/
  __init__.py          — HeimaConfigFlow, HeimaOptionsFlowHandler (coordinatori thin)
  _common.py           — selectors, normalization helpers, _NON_NEGATIVE_INT, ecc.
  _steps_general.py    — general + house signals
  _steps_people.py     — people named + anonymous
  _steps_rooms.py      — rooms (add/edit/remove/import areas)
  _steps_lighting.py   — lighting rooms + zones
  _steps_heating.py    — heating + branches
  _steps_security.py   — security
  _steps_notifications.py — notifications
  _steps_reactions.py  — reactions (stub vuoto per ora)
```

Regole:
- `config_flow.py` diventa `config_flow/__init__.py` (HA lo trova uguale)
- Ogni modulo espone un mixin con i metodi `async_step_*` e helper privati della sezione
- `HeimaOptionsFlowHandler` eredita tutti i mixin
- Nessuna modifica agli schema, ai dati, alla navigazione
- Test suite verde dopo ogni spostamento

---

### Step CF2 — Menu toplevel

**Obiettivo**: navigazione libera tra sezioni.

```
async_step_init → async_show_menu(menu_options={
    "general":       "General & House Signals",
    "people":        "People",
    "rooms":         "Rooms",
    "lighting":      "Lighting",
    "heating":       "Heating",
    "security":      "Security",
    "notifications": "Notifications",
    "reactions":     "Reactions",
    "save":          "Save & Close",
})
```

Cambiamenti:
- Ogni sezione: al submit → `return await self.async_step_init()` (torna al menu)
- Le sottosezioni (people_menu, rooms_menu, ecc.) conservano i loro submenu interni
- Fine wizard per ogni sottosezione: non chiama la sezione successiva ma torna a `async_step_init()`
- Nuova `async_step_save`: chiama `_finalize_options()` + `async_create_entry`
- `_finalize_options()` resta invariato (cross-section validation: orphan rooms in zones, ecc.)

Compatibilità dati: nessun cambiamento al modello opzioni.

---

### Step CF3 — Sezione Reactions

**Obiettivo**: configurare built-in reactions da UI; mute persistito.

#### CF3.1 — Modello dati

Nuovo key in options: `reactions` (dict per-reaction):

```python
OPT_REACTIONS = "reactions"

# Esempio options["reactions"]:
{
  "presence_pattern": {
    "enabled": True,
    "min_arrivals": 5,
    "window_half_min": 15,
    "pre_condition_min": 20,
    "muted": False,
  }
}
```

#### CF3.2 — Catalog built-in

In `const.py` (o `reactions/_catalog.py`): dict statico con le reactions built-in e i loro parametri default + schema. Per v1: solo `PresencePatternReaction`.

```python
BUILTIN_REACTIONS_CATALOG = {
    "presence_pattern": {
        "display_name": "Presence Pattern (Pre-conditioning)",
        "reaction_class": "PresencePatternReaction",
        "defaults": {
            "enabled": False,
            "min_arrivals": 5,
            "window_half_min": 15,
            "pre_condition_min": 20,
            "muted": False,
        },
    }
}
```

#### CF3.3 — Engine auto-registration

Il motore legge `options["reactions"]` in `async_initialize` e `async_reload_options` e registra le reactions abilitate con i parametri configurati.

Questo sostituisce la registrazione manuale esterna (che per ora non esiste per le built-in).

Mute persistito: `_muted_reactions` viene inizializzato da `options["reactions"][id]["muted"]` al momento dell'inizializzazione; le modifiche runtime via `mute_reaction()`/`unmute_reaction()` aggiornano solo la memoria, non le opzioni. Per persistere il mute, l'utente usa la UI (CF3).

#### CF3.4 — UI Reactions step

```
async_step_reactions (menu)
  ├── lista reactions del catalog
  │     - nome, stato (enabled/muted), fire_count live
  │     - azione: "Configura" per ognuna
  └── async_step_reaction_edit_form (per reaction_id)
        - toggle enabled
        - toggle muted (persisted)
        - parametri numerici (min_arrivals, window_half_min, pre_condition_min)
        → salva in options["reactions"][id]
        → torna a async_step_reactions
```

---

### Stato

- CF1: da fare
- CF2: da fare
- CF3: da fare
