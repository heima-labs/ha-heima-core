# Heima — Improvement Plan
**Data:** 2026-04-07
**Input:** spec_audit_2026-04-06.md (finding A1–C5, D1–D3, HS-1–4, HT-1–2, LRN-1–3, INF-1–7)

---

## Legenda priorità

| Priorità | Criterio |
|----------|----------|
| P0 | Bloccante per implementazione corretta o sicurezza del dato |
| P1 | Gap che si manifesta in comportamento scorretto o in assenza di contratto formale richiesto dal codice |
| P2 | Spec non allineata al codice (il codice è corretto, la spec va aggiornata) |
| P3 | Chiarimenti stilistici, disambiguazioni, miglioramenti UX |

---

## Tier 1 — P0: Bloccanti (fare subito)

### IP-01 · Scrivere `CalendarDomain` spec
**Tipo:** Spec nuova
**Finding:** D (spec mancante)
**Problema:** `house_state_spec` e `heating_spec` dipendono da un CalendarDomain non specificato. Senza contratto, l'implementazione è implicita nel codice e non garantita.
**Deliverable:** `docs/specs/domains/calendar_domain_spec.md` con:
- Canonical entities esposte
- API query (calendar_office, calendar_wfh, next_event)
- Semantica "current" vs "next" per workday evidence
- Contratto di integrazione con HouseStateDomain

---

### IP-02 · Definire `IProposalLifecycleHooks` come interfaccia formale
**Tipo:** Spec update
**Finding:** A3, B12, D
**Problema:** Il contratto di delega tra ProposalEngine e plugin non esiste nella spec. Nel codice esiste `ProposalLifecycleHooks` dataclass con 4 callable typed — la spec va allineata e arricchita.
**Deliverable:** Aggiornare `proposal_lifecycle_spec.md` con:
- Firma tipizzata di ogni hook (identica al codice in `lifecycle.py`)
- Comportamento default per ogni hook (cosa fa ProposalEngine se il hook non è implementato)
- Invarianti che ProposalEngine mantiene unconditionally (proposal accettata non riaperta, no identity collision cross-plugin)
- Sezione "identity collision policy": se due plugin restituiscono lo stesso identity_key → errore esplicito

---

### IP-03 · Specificare signal routing conflict resolution (v2)
**Tipo:** Spec update
**Finding:** B5, D
**Problema:** Comportamento non definito quando due ILearningModule emettono segnali incompatibili con confidence ≥ 0.60.
**Deliverable:** Aggiungere sezione "Signal Conflict Resolution" a `inference_engine_spec.md`:
- Strategia default (highest confidence wins? vote? escalate to OBSERVE?)
- Sezione tie-breaking (stessa confidence → conservative wins, cioè OBSERVE su ASSERT)
- Logging requirement: ogni conflict va loggato come warning

---

## Tier 2 — P1: Bug / Comportamento scorretto

### IP-04 · Normalizzare `min_weeks` come policy configurabile per dominio
**Tipo:** Spec + code alignment
**Finding:** LRN-1
**File:** `docs/specs/learning/learning_system_spec.md`, `custom_components/heima/runtime/analyzers/*`
**Problema:** il codice usa già `min_weeks` come gate reale in Presence, Lighting, Composite e Security Presence, ma non come policy canonica configurabile per dominio. `HeatingPatternAnalyzer` oggi riporta `weeks_observed` come evidenza senza applicare un gate `min_weeks` esplicito.
**Fix / Deliverable:**
- formalizzare in spec che `min_weeks` e `min_occurrences` sono policy per family / dominio
- definire una shape di override tipo:
  - `learning.presence.min_weeks`
  - `learning.lighting.min_weeks`
  - `learning.composite.min_weeks`
  - `learning.security_presence_simulation.min_weeks`
  - `learning.heating.min_weeks`
- riallineare progressivamente gli analyzer a leggere tali valori da config/policy invece di usare solo costanti locali
- decidere esplicitamente se `HeatingPatternAnalyzer` debba adottare un vero gate `min_weeks` o restare eccezione documentata

---

## Tier 3 — P2: Spec non allineata al codice (codice corretto)

### IP-05 · Aggiornare spec: scene_signature algorithm (B13)
**Tipo:** Spec update
**Finding:** B13, LRN-3
**Deliverable:** Aggiungere sezione "Scene Signature" a `proposal_lifecycle_spec.md`:
- brightness bucketing: step=32
- color_temp bucketing: step=250K
- sort deterministico degli step
- rationale: tolleranza a minor drift senza falsi negativi

---

### IP-06 · Aggiornare spec: vacation curve formula (B19)
**Tipo:** Spec update
**Finding:** B19, HT-2
**Deliverable:** Aggiungere sezione "Vacation Curve Formula" a `heating_spec.md` con le formule esatte trovate nel codice:
```
ramp_down:  t = start_temp + (min_safety - start_temp) * (hours_from / ramp_down_h)
cruise:     t = min_safety
ramp_up:    t = min_safety + (comfort_temp - min_safety) * (1 - hours_to / ramp_up_h)
eco_only:   t = min_safety   (total_hours < min_total_hours_for_ramp)
quantize:   round(t / temperature_step) * temperature_step
```

---

### IP-07 · Aggiornare spec: manual override detection (B23)
**Tipo:** Spec update
**Finding:** B23
**Deliverable:** Aggiungere a `heating_spec.md`: override rilevato via `preset_mode` attributo HA standard. Valori che triggerano override: `hold`, `manual`, `manualhold`, `override`, `permanenthold`, `temporaryhold`. Fallback: `heima_heating_manual_hold` binary sensor.

---

### IP-08 · Aggiornare spec: temperature quantization (B22)
**Tipo:** Spec update
**Finding:** B22
**Deliverable:** Aggiungere a `heating_spec.md`: quantizzazione via `round()` (non floor/ceil), default `temperature_step=0.5°C`.

---

### IP-09 · Aggiornare spec: hysteresis timer units (HS-2)
**Tipo:** Spec update
**Finding:** HS-2
**Deliverable:** Aggiungere nota a `house_state_spec.md` §7: tutti i valori timer sono in **minuti** (il codice moltiplica per 60 per convertire in secondi).

---

### IP-10 · Aggiornare spec: wake_candidate include `anyone_home` (HS-3)
**Tipo:** Spec update
**Finding:** HS-3
**Deliverable:** Aggiungere `anyone_home` alle condizioni di `wake_candidate` in `house_state_spec.md` §6.2.

---

### IP-11 · Aggiornare spec: relax_candidate sleeping suppression (HS-4)
**Tipo:** Spec update
**Finding:** HS-4
**Deliverable:** Chiarire in `house_state_spec.md` che la suppression di relax quando sleeping è attivo avviene nel state machine resolver (non nel candidato), e documentare perché (evita race condition nella transizione sleeping→relax).

---

### IP-12 · Aggiornare spec: Composite domain status (B14)
**Tipo:** Spec update
**Finding:** B14
**Deliverable:** Chiarire in `proposal_lifecycle_spec.md` che P16 (composite domain) descrive lo stato v1.x attuale, non un target futuro.

---

## Tier 4 — P3: Chiarimenti e miglioramenti minori

### IP-13 · Spec: DomainResultBag vs CanonicalState coherence (B4)
**Tipo:** Spec update
**Finding:** B4
**Deliverable:** Aggiungere nota a `heima_v2_spec.md`: plugin leggono sempre CanonicalState (ciclo precedente). DomainResultBag è read-only per dominio corrente solo in Apply phase. Se divergono, CanonicalState è la view autorevole durante evaluation.

---

### IP-14 · Spec: SnapshotStore TTL semantics (B2)
**Tipo:** Spec update
**Finding:** B2
**Deliverable:** Chiarire in `inference_engine_spec.md`: TTL calcolato da `snapshot.ts` (momento di creazione), non da ultimo accesso.

---

### IP-15 · Spec: ILearningModule init state (B15)
**Tipo:** Spec update
**Finding:** B15
**Deliverable:** Aggiungere a `inference_engine_spec.md`: `infer()` prima del primo `analyze()` restituisce lista vuota (zero signals). Nessun stato interno richiesto prima dell'analisi.

---

### IP-16 · Spec: INDEX — disambiguare DAG v1 hardcoded vs v2 declarative (A1)
**Tipo:** Spec update
**Finding:** A1
**Deliverable:** Aggiungere nota in `INDEX.md`: v1 usa DAG hardcoded nell'engine; v2 introduce DAG dichiarativo con topological sort. Non sono implementazioni alternative — v2 sostituisce v1 quando schedulato.

---

## Tier 5 — v2 RFC: Scheduling decision richiesta

### IP-17 · Inference Engine v2 — schedulare o congelare
**Tipo:** Decisione architetturale + roadmap
**Finding:** INF-1 through INF-7
**Status attuale:** 0% implementato. Spec è Draft/RFC.
**Decisione richiesta:** Schedulare per v2 milestone o marcare come "on-hold" in INDEX?
**Se schedulato:** ~2000 righe di codice nuovo. Ordine suggerito:
1. `HouseSnapshot` + `SnapshotStore` (storage + TTL)
2. `InferenceSignal` hierarchy + `Importance` enum
3. `ILearningModule` protocol
4. 1 built-in module (WeekdayState — più semplice)
5. `SignalRouter`
6. Engine integration
7. Domain consumption (house_state prima)

---

## Riepilogo per priorità

| ID | Priorità | Tipo | Effort |
|----|----------|------|--------|
| IP-01 | P0 | Spec nuova | Alto |
| IP-02 | P0 | Spec update | Medio |
| IP-03 | P0 | Spec update | Basso |
| IP-04 | P1 | Code fix | Basso |
| IP-05 | P2 | Spec update | Basso |
| IP-06 | P2 | Spec update | Basso |
| IP-07 | P2 | Spec update | Basso |
| IP-08 | P2 | Spec update | Basso |
| IP-09 | P2 | Spec update | Basso |
| IP-10 | P2 | Spec update | Basso |
| IP-11 | P2 | Spec update | Basso |
| IP-12 | P2 | Spec update | Basso |
| IP-13 | P3 | Spec update | Basso |
| IP-14 | P3 | Spec update | Basso |
| IP-15 | P3 | Spec update | Basso |
| IP-16 | P3 | Spec update | Basso |
| IP-17 | RFC | Arch decision | Alto |

**Unico code fix urgente: IP-04**
**Nuova spec urgente: IP-01 (CalendarDomain)**
**Spec update più impattante: IP-02 (IProposalLifecycleHooks)**
