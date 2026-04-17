# Heima — Spec Audit
**Data:** 2026-04-06
**Scope:** Spec review (pre code audit). File analizzati: INDEX, core_product_spec, heima_spec_v1, heima_v2_spec, learning_system_spec, proposal_lifecycle_spec, inference_engine_spec, house_state_spec, heating_spec, security_presence_simulation_spec, domain_framework_spec, input_normalization_layer_spec, policy_plugin_framework_spec.

---

## Valutazione complessiva: 3.5/5

Le spec core v1.x sono mature (4/5). Le RFC v2 e le spec di framework hanno gap critici.

---

## A — Contraddizioni inter-spec

| ID | Problema | Spec coinvolte | Severità |
|----|----------|---------------|----------|
| A1 | Hardcoded DAG v1 vs declarative DAG v2: transizione non marcata chiaramente in INDEX | heima_spec_v1, heima_v2_spec | Bassa |
| A2 | Priority order flat list vs two-layer (hard+substate): terminologia diversa, semantica coerente | heima_spec_v1, house_state_spec | Bassa |
| A3 | ProposalEngine centrale vs plugin-owned lifecycle hooks: contratto di delega non esiste | learning_system_spec, proposal_lifecycle_spec | **Alta** |
| A4 | Heating legge house_state, ma CalendarDomain (upstream) non ha spec propria | heating_spec, house_state_spec | Media |

---

## B — Ambiguità e gap logici

| ID | Problema | Spec | Severità |
|----|----------|------|----------|
| B1 | Domain vs Plugin: terminologia usata in modo intercambiabile senza definire la relazione in v2 | heima_v2_spec, domain_framework_spec | **Alta** |
| B2 | SnapshotStore TTL: calcolato da snapshot.ts (creazione) o da ultimo async_load()? | heima_v2_spec, inference_engine_spec | Media-Alta |
| B3 | InvariantCheck debounce state: persisted (sopravvive a restart) o in-memory? Storage location? | heima_v2_spec | **Alta** |
| B4 | DomainResultBag + CanonicalState: un plugin può leggere entrambi; quale view è coerente se divergono? | heima_v2_spec | Media |
| B5 | Signal routing conflict: due ILearningModule emettono HouseStateSignal con predicted_state diversi, entrambi confidence > 0.60 — chi vince? | heima_v2_spec | Media-Alta |
| B6 | Occupancy mode "none": valore di heima_occupancy_<room>_source non specificato | heima_spec_v1 | Bassa |
| B7 | People presence: ordine di evaluation e quorum voting su sorgenti multiple non formalizzati | heima_spec_v1 | Media |
| B8 | Lighting scene apply fallback: "may fallback to light.turn_off" — contratto o euristica? | heima_spec_v1 | Bassa-Media |
| B9 | heima.set_mode timing: se chiamato durante un ciclo di evaluation, quando prende effetto? | heima_spec_v1 | Media |
| B10 | EventRecorderBehavior source attribution: finestra temporale per distinguere "heima" vs "user" non specificata | learning_system_spec | Media |
| B11 | HeatingPatternAnalyzer "partial": quali feature mancano? | learning_system_spec | Bassa |
| B12 | Plugin lifecycle hooks: identity_key(), followup_slot_key(), fallback_followup_match(), should_suppress_followup() citati ma mai definiti come interfaccia formale | proposal_lifecycle_spec | **Alta** |
| B13 | scene_signature algorithm: come viene calcolato? Quale tolleranza su brightness/color? | proposal_lifecycle_spec | Media |
| B14 | Composite domain (P16): la spec descrive stato corrente o target v1.x? | proposal_lifecycle_spec | Media |
| B15 | ILearningModule: cosa fa infer() prima del primo analyze()? Stato interno non inizializzato? | inference_engine_spec | Bassa-Media |
| B16 | Workday evidence: come HouseStateDomain interroga CalendarDomain? Ogni ciclo? Cached? | house_state_spec | Media |
| B17 | relax_mode: durata minima prima che sia considerato "explicit" (attivazione immediata)? | house_state_spec | Bassa-Media |
| B18 | media_active: quali entity types e quale threshold di "active"? | house_state_spec | Bassa-Media |
| B19 | Vacation curve: formula non specificata (lineare? esponenziale? piecewise?) | heating_spec | **Alta** |
| B20 | Vacation curve start temperature: fallback se unavailable al momento di attivazione? | heating_spec | Media |
| B21 | vacation_comfort_temp preheat: quando viene applicato, per quanto, handoff timing? | heating_spec | Media |
| B22 | Temperature quantization: round, floor, o ceiling? Default di temperature_step? | heating_spec | Bassa-Media |
| B23 | Manual override detection: quale campo del climate entity? preset_mode? hold_mode? Custom attr? | heating_spec | Media |
| B24 | Security presence simulation: algoritmo di generazione nightly plan non specificato | security_presence_simulation_spec | **Alta** |
| B25 | Seasonality/sunset: soglia di "darkness" non definita (sunset? sunset+30m?) | security_presence_simulation_spec | Media |
| B26 | Evidence thresholds per simulation: min reactions, min room count, min event density — nessun valore | security_presence_simulation_spec | Media |
| B27 | Behavior hook point signatures: on_snapshot(), <domain>_policy(), apply_filter() non formalizzati | domain_framework_spec | Media-Alta |
| B28 | Orchestrator apply plan: esecuzione sequenziale o parallela per dominio? Dedup semantics? | domain_framework_spec | Media |
| B29 | Built-in fusion strategies (any_of, all_of, quorum): algoritmi di implementazione mancanti | input_normalization_layer_spec | Media-Alta |
| B30 | Dwell state machine: persisted o in-memory? Storage location? | input_normalization_layer_spec | **Alta** |

---

## C — Idee architetturalmente deboli

| ID | Problema | Severità | Note |
|----|----------|----------|------|
| C1 | "Invisibility" success metric: non misurabile, rischio di silent failure non distinguibile da "sistema funzionante" | Media | Product philosophy; non blocca implementazione |
| C2 | Proposal fatigue: nessuna strategia di filtering/batching per volume di proposal | Media | UX risk se learning genera molte proposal |
| C3 | Source discrimination senza temporal heuristics: rischio di stagnazione del learning (sistema non rinforza accettazione implicita) | Media-Alta | Se Heima agisce e utente non interviene, apprendimento non migliora |
| C4 | Invariant checks senza definizione formale di "invariant": mix di structural + safety + timing checks; pluggabilità non dichiarata | Media | Rende difficile per plugin author capire cosa è un invariant |
| C5 | OutcomeTracker (v2) non integrato con learning system: l'esito di una reazione non retroalimenta il learning | Media | Opportunità di design mancata |

---

## D — Spec mancanti (bloccanti per implementazione)

| Spec mancante | Utilizzata da | Impatto |
|--------------|--------------|---------|
| CalendarDomain spec | house_state_spec, heating_spec | Media-Alta: house state workday evidence e heating dipendono da questo contratto |
| IProposalLifecycleHooks interfaccia | proposal_lifecycle_spec | Alta: ProposalEngine non può delegare semantiche ai plugin senza contratto formale |
| Signal routing conflict resolution | heima_v2_spec | Alta: comportamento multi-modulo inference v2 indefinito |

---

## E — Tensione architetturale principale (discussa)

**ProposalEngine + Plugin lifecycle hooks**

La spec vuole che ProposalEngine rimanga il punto centrale di decisione, delegando semantiche domain-specific ai plugin. Il design è corretto. Il problema è che il contratto di delega non esiste come tipo formale.

Conseguenze concrete:
1. **Identity collision**: se due plugin restituiscono lo stesso `identity_key`, ProposalEngine non sa se fare merge o errore
2. **Invarianti non garantiti**: non è dichiarato quali invarianti ProposalEngine mantiene *nonostante* i plugin (es. "una proposal accettata non viene riaperta automaticamente")
3. **Fallback impliciti**: se un plugin non implementa `identity_key()`, il default di ProposalEngine non è specificato

**Soluzione minima**: definire `IProposalLifecycleHooks` con contratto per ogni metodo, comportamento default, e lista di invarianti che ProposalEngine mantiene unconditionally.

---

## Scorecard per spec

| Spec | Completeness | Clarity | Implementability | Overall |
|------|-------------|---------|-----------------|---------|
| core_product_spec | 4/5 | 4/5 | 3/5 | 4/5 |
| heima_spec_v1 | 4/5 | 4/5 | 3/5 | 4/5 |
| house_state_spec | 3.5/5 | 3.5/5 | 3/5 | 3.5/5 |
| heima_v2_spec | 4/5 | 3.5/5 | 3/5 | 3.5/5 |
| learning_system_spec | 4/5 | 3.5/5 | 3/5 | 3.5/5 |
| inference_engine_spec | 4/5 | 3.5/5 | 3/5 | 3.5/5 |
| proposal_lifecycle_spec | 3.5/5 | 3/5 | 2.5/5 | 3/5 |
| domain_framework_spec | 3.5/5 | 3/5 | 2.5/5 | 3/5 |
| heating_spec | 3/5 | 3/5 | 2.5/5 | 3/5 |
| input_normalization_layer_spec | 3/5 | 3/5 | 2/5 | 2.5/5 |
| policy_plugin_framework_spec | 2.5/5 | 2.5/5 | 2/5 | 2.5/5 |
| security_presence_simulation_spec | 2.5/5 | 2.5/5 | 1.5/5 | 2.5/5 |

---

## Prossimi step

- [x] **Code audit — House State** ✅
- [x] **Code audit — Heating** ✅
- [x] **Code audit — Learning / ProposalEngine** ✅
- [x] **Code audit — Inference engine** ✅
- [ ] **Plan di improvement** — indirizzare i gap trovati, partendo dai bloccanti

---

## Code Audit — Inference Engine (v2)

**Conformità: 0% — Non implementato. È una spec Draft/RFC, non ancora schedulata.**

Il codebase implementa il v1 ProposalEngine (pattern matching su EventStore). L'Inference Engine v2 (predictive inference con SnapshotStore e ILearningModule) non ha nessuna linea di codice.

**Cosa manca completamente:**
- `runtime/inference/` directory (non esiste)
- `SnapshotStore` (MAX_RECORDS=10K, TTL=90d, persistenza HA Storage)
- `HouseSnapshot` dataclass
- `InferenceContext`
- `InferenceSignal` hierarchy (base + HouseStateSignal, OccupancySignal, HeatingSignal, LightingSignal)
- `Importance` enum (OBSERVE/SUGGEST/ASSERT)
- `ILearningModule` protocol (analyze + infer + diagnostics)
- 5 built-in modules (WeekdayState, RoomCorrelation, HeatingPreference, LightingPattern, HouseStateInference)
- `SignalRouter`
- Integrazione in engine.py (collect_signals, record_snapshot_if_changed)
- Domain signal consumption (house_state, heating, lighting)

**Gap della spec confermati come non implementati:**
- **B2 (TTL semantics)**: non rilevante oggi, SnapshotStore non esiste
- **B3 (InvariantCheck debounce persistence)**: non implementato, stato in-memory (se esiste)
- **HS-1**: confermato — nessun dominio consuma InferenceSignal

**Valutazione**: non è un bug, è uno status corretto per una spec non schedulata. L'implementazione richiederebbe ~2000 righe di codice nuovo ben definito dalla spec.

### Divergenze (tutte di status "non implementato — spec è RFC")

| ID | Componente | Severità |
|----|-----------|----------|
| INF-1 | SnapshotStore + HouseSnapshot | Alta (RFC) |
| INF-2 | InferenceSignal hierarchy + Importance enum | Alta (RFC) |
| INF-3 | ILearningModule protocol | Alta (RFC) |
| INF-4 | 5 built-in learning modules | Alta (RFC) |
| INF-5 | SignalRouter | Alta (RFC) |
| INF-6 | Engine integration (collect_signals, snapshot recording) | Alta (RFC) |
| INF-7 | Domain signal consumption (house_state, heating, lighting) | Alta (RFC) |

---

## Code Audit — Learning / ProposalEngine

**Conformità generale: ~94% — Sistema solido, gap critici della spec risolti nel codice**

### Gap critici della spec che risultano già risolti nel codice

**A3/B12 — Plugin lifecycle hooks**: il gap era nella spec, non nel codice. L'interfaccia `ProposalLifecycleHooks` esiste in `lifecycle.py`, con i 4 metodi (`identity_key`, `followup_slot_key`, `fallback_followup_match`, `should_suppress_followup`) come callable typed. ProposalEngine delega correttamente senza hardcoding su `reaction_type`. La spec va aggiornata per descrivere questa interfaccia.

**B13/B14 — scene_signature algorithm**: implementato in `lifecycle.py`. Bucketing: brightness step=32, color_temp step=250K. Sort deterministico degli step. Coarse quanto basta per tollerare minor drift.

### Architettura conforme

- Separazione hot path / offline path rispettata: nessun analyzer gira in `on_snapshot()`
- EventStore: max=5000 record, TTL=60 giorni, HA Storage, API completa
- Source discrimination: `source="heima"` vs `source="user"` su tutti i recorder; analyzer filtrano su `source="user"`
- Training thresholds: baseline min_occurrences=5, min_weeks=2, min_confidence=0.4
- Proposal lifecycle: 3 stati persistiti (pending/accepted/rejected), staleness derivata, pruning automatico ogni 6h (threshold 45 giorni)
- Admin-authored proposals: path separato con `origin="admin_authored"`, 4 template implementati

### Divergenze trovate

| ID | Severità | Descrizione |
|----|----------|-------------|
| LRN-1 | Media | **`min_weeks` non è ancora normalizzato come policy per dominio**: Presence, Lighting, Composite e Security Presence hanno un gate reale sulle settimane distinte; Heating espone `weeks_observed` nei diagnostics ma non applica ancora un `min_weeks` configurabile come gate. La spec v1 parlava di soglia uniforme, ma il codice è oggi semicoerente e per-family. |
| LRN-2 | Bassa | **Composite room assist manca `fallback_followup_match`**: lighting ha il hook implementato (per tuning_suggestion), composite no. Non bloccante per v1 dato che l'identity è già coarse. |
| LRN-3 | Info | **Spec A3/B12/B13/B14 vanno aggiornate**: il codice ha già risolto questi gap. La spec descrive hook e scene_signature come "mancanti" — in realtà sono implementati e documentati solo nel codice. |

---

## Code Audit — Heating

**Conformità generale: ~92% — Dominio solido, nessuna divergenza bloccante**

### Vacation curve — formula trovata nel codice

La spec non specifica la formula; quella implementata è:

```
ramp_down:  t = start_temp + (min_safety - start_temp) * (hours_from / ramp_down_h)
cruise:     t = min_safety
ramp_up:    t = min_safety + (comfort_temp - min_safety) * (1 - hours_to / ramp_up_h)
eco_only:   t = min_safety   (se vacation breve, total_hours < min_total_hours_for_ramp)

quantize:   round(t / temperature_step) * temperature_step
```

Safety floor hardcoded (conforme spec):
- outdoor ≤ 0°C → floor = max(vacation_min_temp, 17.0)
- 0°C < outdoor ≤ 3°C → floor = max(vacation_min_temp, 16.5)
- else → floor = vacation_min_temp

### Manual override detection

Usa `preset_mode` dell'entità climate (attributo standard HA). Valori che triggerano override: `hold`, `manual`, `manualhold`, `override`, `permanenthold`, `temporaryhold`. Fallback a `heima_heating_manual_hold` binary sensor.

### Divergenze trovate

| ID | Severità | Descrizione |
|----|----------|-------------|
| HT-1 | Bassa | **Policy tree non "guard-first"**: la spec descrive "manual override guard PRIMA di tutto"; nel codice il guard viene applicato in `_finalize_heating_target()` dopo aver calcolato il target. Il risultato finale è corretto, ma l'ordine logico non rispecchia la spec. |
| HT-2 | Info | **Spec §B19 chiarita dal codice**: la vacation curve usa interpolazione lineare. La spec mancava la formula (gap B19); ora documentata. |

---

## Code Audit — House State

**Conformità generale: ~91% — Dominio molto solido**

### Conforme
- Due layer di risoluzione (hard + substate) implementati correttamente
- Priority order: manual_override > vacation > guest > away > sleeping > relax > working > home — esatto
- sleep_candidate: tutte le condizioni (sleep_window, media_off, charging_min_count)
- work_candidate + workday evidence resolution: ordine esatto (calendar_office → false, calendar_wfh → true, workday_entity, default=true)
- Hysteresis state machine: in-memory con `time.monotonic()`, corretto
- Configurable bindings: tutti presenti (vacation, guest, sleep_window, relax, work_window, media_active, sleep_charging, workday_entity, sleep_requires_media_off, sleep_charging_min_count)
- Canonical entities: tutte + 2 diagnostic aggiuntive (heima_house_state_pending_candidate, heima_house_state_pending_remaining_s)
- Diagnostics payload completo

### Divergenze trovate

| ID | Severità | Descrizione |
|----|----------|-------------|
| HS-1 | Media | **HouseStateSignal non implementato**: la v2 spec prevede consumo di InferenceSignal con min_confidence=0.60. Non esiste nel codice. Da trattare come feature v2 non ancora implementata. |
| HS-2 | Bassa | **Timer: unità non chiarita nella spec**. La spec §7 lista valori (10, 2, 5, 2, 10) senza specificare secondi o minuti. Il codice assume minuti (moltiplica per 60). Implementazione internamente coerente, ma la spec va chiarita. |
| HS-3 | Bassa | **wake_candidate aggiunge `anyone_home`** non menzionato nella spec §6.2. Probabilmente corretto (home substate implica presenza), ma la spec va allineata. |
| HS-4 | Bassa | **relax_candidate non esclude sleeping** nel candidato input — la soppressione avviene nel state machine resolver. Non è un bug, ma la spec descrive l'esclusione come parte del candidato stesso. |
