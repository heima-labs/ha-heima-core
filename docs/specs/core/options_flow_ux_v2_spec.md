# Heima — Options Flow UX v2 SPEC

**Status:** Active v2 UX and persistence contract
**Created:** 2026-03-17

---

## Motivazione

Il config flow v1 presentava tre problemi principali:

1. **Nessuna visibilità della configurazione attuale** nei menù: l'utente non sapeva cosa fosse configurato senza entrare in ogni sotto-step.
2. **UX confusa per la heating vacation curve**: selettore del tipo di branch e parametri nello stesso form — cambiare il tipo richiedeva un submit intermedio per aggiornare i campi visibili.
3. **Reactions menu silenziosamente vuoto**: dopo aver accettato una proposta nel config flow ma prima di salvare, il menu Reazioni risultava vuoto perché `_get_registered_reaction_ids` leggeva solo l'engine post-save, non la sessione corrente.

## Contratto di questa spec

Questa spec descrive il comportamento utente e il contratto di persistenza dell'Options Flow.
Non richiede la lettura del codice per capire:
- quali step esistono
- quali dati l'utente può configurare
- quando una modifica deve essere salvata
- quali oggetti runtime devono risultare configurabili o ricostruibili dopo il salvataggio

Regola normativa:
- l'Options Flow è la fonte di verità del profilo configurato dall'utente
- il runtime deve potersi ricostruire integralmente a partire dal payload persistito prodotto da
  questo flow

---

## Obiettivi e non-obiettivi

Obiettivi:
- rendere visibile lo stato configurato senza entrare in ogni sotto-step
- permettere salvataggi incrementali senza perdere coerenza del profilo
- garantire che le proposal accettate producano configurazione runtime ricostruibile

Non-obiettivi:
- descrivere dettagli interni di rendering dell'interfaccia oltre ciò che è necessario al
  contratto UX
- imporre una specifica organizzazione dei file o dei mixin del flow

---

## Decisioni di prodotto e contratto

### D1 — Status block nel menù principale (init)

Il menù `init` mostra un blocco di stato nella `description`, con una riga per ogni sezione configurabile. Ogni riga indica il nome della sezione e il suo stato corrente.

**Formato (un placeholder `status_block`, testo multi-riga separato da `\n`):**
```
Motore: attivo
Persone (3): Stefano, Elena, Marco
Stanze (4): Soggiorno, Cucina, Studio, Camera
Illuminazione: 3/4 stanze
Riscaldamento: climate.termostato | 2 branch
Sicurezza: disabilitata
```

**Nota tecnica:** HA non supporta `description_placeholders` nelle singole voci `menu_options` — il testo delle voci è statico. Il blocco di stato va quindi nella `description` del menù tramite un singolo placeholder `{status_block}`.

### D2 — Configuration summary nei menù di secondo livello

Ogni menù di secondo livello mostra un riassunto della configurazione attuale tramite `description_placeholders`.

| Menù | Placeholder | Esempio |
|------|-------------|---------|
| `people_menu` | `summary` | `Configurate: 3: Stefano, Elena, Marco` |
| `rooms_menu` | `summary` | `Configurate: 4: Soggiorno, Cucina, Studio, Camera` |
| `lighting_rooms_menu` | `summary` | `Scene configurate: 3/4 stanze` |
| `heating_branches_menu` | `summary` | `climate.termostato \| 2 branch` |

### D3 — Heating branch: flusso in due step

Il flusso di configurazione di un heating branch override è stato suddiviso:

1. `heating_branch_select` — mostra solo il selettore del tipo di branch (`vacation_curve`, `fixed_temp`, `disabled`)
2. `heating_branch_edit_form` — mostra solo i parametri specifici del tipo selezionato (no branch selector)

Se il branch selezionato è `disabled`, il form parametri viene saltato e si torna direttamente al menù.

### D4 — Reactions: merge engine + sessione corrente

Il menù Reazioni deve mostrare sia:
1. reaction già ricostruite dal runtime
2. reaction accettate nella sessione corrente ma non ancora salvate definitivamente

Il payload persistito deve includere una label leggibile per le reaction accettate, così che la UI
possa mostrarle senza dipendere dal runtime già ricostruito.

### D5 — Proposal action configuration

Dopo che l'utente accetta una o più proposte nel passo `proposals`, il flow non torna subito a `init` ma apre un nuovo step `proposal_configure_action` per ciascuna proposta accettata (una alla volta).

**Step `proposal_configure_action`:**

| Campo | Tipo | Note |
|-------|------|-------|
| `action_entities` | entity selector (`scene`, `script`), **multiple**, opzionale | Le entity HA da attivare quando la reaction si innesca |
| `pre_condition_min` | intero positivo, default 20 | Anticipo in minuti rispetto all'orario tipico |

La descrizione della proposal è mostrata via `description_placeholders: {proposal_description}`.

**Comportamento:**
- Se `action_entities` è valorizzato, vengono normalizzati in step eseguibili dal runtime:
  - `scene.*` → `{"domain": "lighting", "target": entity_id, "action": "scene.turn_on", "params": {"entity_id": entity_id}}`
  - `script.*` → `{"domain": "script", "target": entity_id, "action": "script.turn_on", "params": {"entity_id": entity_id}}`
- Se vuoto: `steps = []` — la reaction viene registrata senza azione (configurabile in seguito)
- `pre_condition_min` sovrascrive il default nel config della reaction

**Contratto di normalizzazione:**
- lo step salvato deve rappresentare una richiesta eseguibile dal runtime, non una scelta UI grezza
- la shape persistita deve essere sufficiente per ricostruire la reaction senza dipendere da stato
  temporaneo della sessione UI
- accettare una proposal non deve mai produrre uno stato “accepted but not executable”

**Nota runtime aggiornata:**
- `scene.turn_on` continua a passare dal `LightingDomain`; il runtime marca anche un batch best-effort di luci attese della room/area per migliorare la provenance multi-entità nel learning.
- `script.turn_on` è eseguibile come passo runtime reale; gli effetti osservati successivi vengono attribuiti con provenance batch-level a finestra breve, come fallback meno preciso rispetto al caso `scene`.

### D5.1 Provenance e correlation nel contesto UX

L'Options Flow non registra direttamente eventi di learning, ma deve produrre configurazioni che
non rompano i contratti del learning runtime.

Regola di configurazione:
- il flow `Rooms` definisce la semantica primaria delle entità room-scoped
- il flow `Learning` aggiunge solo segnali globali extra e binding ambientali (`outdoor_*`,
  `weather_entity`, `context_signal_entities`)
- il runtime di learning SHOULD therefore treat `rooms[*].sources` as the base room-scoped learning
  source set, with `learning.context_signal_entities` as additive extras
- l'evoluzione preferita della UI è un toggle per-source nel flow `Rooms` che renda esplicito se
  una source deve partecipare al learning (`learning_enabled`)
- questa separazione evita di costringere l'utente a duplicare la stessa modellazione stanza in più
  punti della UI

Regola di qualità del segnale:
- il fatto che un'entità compaia in `rooms[*].sources` non implica che debba essere imparata in modo
  cieco
- il learning runtime SHOULD preferire solo segnali stabili e già semanticamente normalizzati
- entità molto rumorose o puramente impulsive possono restare utili per occupancy senza diventare
  automaticamente buoni input per inferenze più ricche

Regola di semantica UX:
- la UI SHOULD rendere comprensibile la differenza tra:
  - entità usate per capire **quando** avviene un comportamento
  - entità osservate per capire **cosa** ha fatto l'utente
- esempio canonico:
  - `sensor.studio_lux` può essere un trigger signal del learning
  - `light.studio_main` può essere una response osservata dal learner lighting

- **Provenance**: il runtime deve poter distinguere tra effetti generati dall'utente ed effetti
  generati da Heima, per evitare di apprendere dai propri output.
- **Correlation**: il runtime deve poter collegare più cambi entità che appartengono alla stessa
  azione logica, ad esempio una scena o uno script che tocca più luci.

Per questo motivo la normalizzazione delle `action_entities` non può limitarsi a salvare un
riferimento simbolico della UI: deve produrre uno step eseguibile che attraversi i normali percorsi
runtime, così che provenance e `correlation_id` possano essere applicati correttamente quando gli
effetti vengono osservati.

Contratto di sessione:
- se più proposal vengono accettate insieme, la configurazione delle azioni deve avvenire una
  proposta alla volta, in ordine deterministico
- la sessione del flow deve poter mantenere questo stato intermedio senza richiedere che il runtime
  sia già stato ricostruito

Contratto di persistenza:
- il salvataggio finale deve aggiornare `configured[proposal_id]["steps"]`
- il salvataggio finale deve aggiornare `configured[proposal_id]["pre_condition_min"]`
- questi campi devono essere sufficienti per ricostruire la reaction senza rileggere la sessione UI

Future extension point:
- una proposal MAY in futuro esporre più `acceptance modes`
- ogni mode rappresenterebbe un diverso modo supportato di concretizzare la stessa behavior appresa
- la UX di v1 non deve assumerlo ancora; oggi il flow gestisce un solo acceptance path effettivo per
  proposal

---

## Invarianti

- il payload persistito dell'Options Flow è autosufficiente per ricostruire il runtime
- una scelta UI non deve essere persistita in forma ambigua o non eseguibile
- la UI può mostrare stato di sessione non ancora salvato, ma non deve confonderlo con stato runtime
- l'accettazione di una proposal e la sua configurazione devono essere atomicamente riconducibili a
  un payload persistito coerente

---

## Stato implementazione

| # | Descrizione | Stato |
|---|-------------|-------|
| TODO-1 | Status block in `init` con placeholder separati per sezione | ✓ completato |
| TODO-2 | `_update_options(updates)` — aggiornamento immediato memoria + disco | ✓ completato |
| TODO-3 | Selective reload in `_async_entry_updated` via `STRUCTURAL_OPTION_KEYS` | ✓ completato |
| TODO-4 | Save-per-step per chiavi strutturali (people, rooms, lighting) | ✓ completato |
| TODO-5 | Reaction label leggibile nella multi_select mute + salvataggio in `labels` | ✓ completato |
| TODO-6 | `proposal_configure_action` — configurazione azioni per proposta accettata | ✓ completato |

---

## Out of scope

- Aggiunta di nuovi step o domini
- Backward compatibility con entry versioni precedenti
