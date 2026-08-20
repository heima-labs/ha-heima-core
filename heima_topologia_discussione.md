# Heima — Discussione sulla Topologia Spaziale
**Stato**: Documento di analisi pre-spec — approccio rivisto dopo review approfondita, v. §10  
**Data**: 2026-08-17 (revisione: 2026-08-18)  
**Autore**: Stefano (con input da Vibe)  
**Scopo**: Raccolta strutturata delle riflessioni sulla gestione della topologia spaziale in Heima (stanze, porte, finestre, balconi, cantine, garage, orientamento).

> **Nota di revisione**: le §§2-7 documentano il ragionamento iniziale (easy-floorplan come fonte dati,
> modello geometrico, inferenza automatica delle connessioni). Restano come riferimento storico, ma
> sono superate dal modello in **§10**, emerso da una review approfondita: approccio grafo-first,
> tool-agnostic, in due fasi, con l'obiettivo esplicito di evitare lock-in su strumenti di terze parti
> e di riusare i registri/pattern già esistenti in Heima invece di introdurne di nuovi.

---

## 1. Contesto e Motivazioni

### 1.1 Situazione attuale di Heima
Heima **già importa automaticamente** stanze e dispositivi da Home Assistant:

- **Stanze**: Da **HA Area Registry** (1:1 mapping con `OPT_ROOMS` in Heima).
  - Funzione chiave: `_ha_area_inventory()` in `coordinator.py` e `config_flow/__init__.py`.
  - Meccanismo: `async_get(hass).async_list_areas()` → lista di `{"area_id": "area.cucina", "display_name": "Cucina"}`.
  - Reconciliation automatica: `_reconcile_rooms()` allinea le aree HA con le stanze interne di Heima.

- **Dispositivi**: Da **HA Entity Registry** (associati a stanze tramite `area_id`).
  - Funzione chiave: `discover_binding_candidates()` in `discovery.py`.
  - Meccanismo: Per ogni entità, estrae `area_id` e suggerisce binding basati su `device_class`:
    | `device_class`          | Binding suggerito          | Categoria       |
    |-------------------------|----------------------------|-----------------|
    | `motion/occupancy`      | `room_occupancy_source`    | presence        |
    | `door/window/opening`   | `security_contact`         | security        |
    | `humidity`              | `activity_shower_humidity` | activity        |

**Limite attuale**: Heima **non ha alcuna informazione sulla topologia spaziale**.
- Non sa **come le stanze sono connesse** tra loro.
- Non sa **dove sono le porte/finestre** rispetto alle stanze.
- Non sa **l’orientamento** delle stanze (nord/sud/est/ovest).

Questo limita:
- **Security**: Non può distinguere porte esterne da interne per logiche di allarme.
- **Occupancy**: Non può inferire movimenti logici tra stanze adiacenti.
- **Activity**: Non può contestualizzare attività in base alla posizione (es: "cucina" vs "camera").
- **HouseState**: Non può validare coerenza (es: "tutti a casa" con porta esterna aperta).

---

### 1.2 Obiettivi
Aggiungere a Heima la **consapevolezza spaziale** per:

1. **Topologia**: Grafico delle connessioni tra stanze (adiacenza, porte, finestre).
2. **Tipologie di aree**: Distinzione tra stanze interne, balconi, garage, cantine, aree esterne.
3. **Coordinate spaziali**: Posizione (x,y) delle stanze in un sistema locale.
4. **Orientamento**: Allineamento del floorplan rispetto al nord (per automazioni basate su sole/luce).

---

## 2. Fonti Dati per la Topologia

### 2.1 Opzioni analizzate

| Fonte               | Dati disponibili               | Topologia | Accesso programmatico | Integrazione con Heima | Scelto |
|---------------------|---------------------------------|-----------|------------------------|-------------------------|--------|
| **HA Area Registry** | Liste di aree (`area_id`, `name`) | ❌ No      | ✅ Sì                  | ✅ Già integrato         | ⚠️ Base |
| **ha-floorplan**     | SVG + YAML mapping              | ❌ No      | ❌ No                  | ❌ Difficile            | ❌ No   |
| **easy-floorplan**   | **JSON strutturato**            | ✅ Sì      | ✅ Sì (file JSON)      | ✅ Facile               | ✅ **SÌ** |

### 2.2 easy-floorplan: Dettagli
**Repo**: [nicosandller/easy-floorplan](https://github.com/nicosandller/easy-floorplan)  
**Vantaggi**:
- Editor **drag-and-drop** per muri, porte, finestre, mobili, dispositivi.
- **Export in JSON** con struttura ben definita.
- **Binding diretto** a entità HA (porte, finestre, sensori, ecc.).
- Supporto **multi-piano** (`floors` array).
- Progetto **attivo** (1.6k star, 197 fork).

**Struttura JSON rilevante**:
```json
{
  "floors": [
    {
      "id": "ground_floor",
      "walls": [
        {"x": 100, "y": 100, "length": 200, "angle": 0}
      ],
      "openings": [
        {
          "id": "front_door",
          "type": "door",
          "x": 150, "y": 100, "length": 40, "angle": 0,
          "entity": "binary_sensor.front_door"
        }
      ],
      "areas": [
        {
          "id": "living_room",
          "name": "Soggiorno",
          "points": [{"x": 100, "y": 100}, {"x": 300, "y": 100}, ...]
        }
      ]
    }
  ]
}
```

**Come usarlo in Heima**:
1. Leggere il file JSON da `/config/lovelace/easy-floorplan-{name}.json`.
2. Parsare il JSON per estrarre stanze, porte, muri.
3. Inferire connessioni tra stanze in base alla posizione delle porte.
4. Arricchire con metadati aggiuntivi (tipologie, orientamento, ecc.).

---

## 3. Modello Dati Proposto

### 3.1 Struttura di base
```json
{
  "metadata": {
    "north_angle": 30,                          // Rotazione floorplan vs nord (gradi)
    "house_center": {"x": 250, "y": 150},      // Centro della casa (per calcoli orientamento)
    "reference_gps": {"lat": 45.4642, "lon": 9.1900}  // Opzionale: allineamento geospaziale
  },
  "rooms": [
    {
      "room_id": "living_room",
      "display_name": "Soggiorno",
      "room_type": "indoor",                   // indoor | balcony | garage | basement | outdoor
      "area_id": "area.living_room",           // Riferimento a HA Areas
      "floor": 0,                              // Piano (0 = terra, -1 = cantina, 1 = primo piano)
      "coordinates": {"x": 100, "y": 150},    // Posizione nel floorplan
      "is_outdoor": false,                     // True per balconi, giardini
      "is_separate": false,                    // True per garage, cantine (accesso indipendente)
      "access_type": null,                     // direct | stairs | elevator | external_path
      "sun_exposure": ["east", "south"],       // Calcolato automaticamente
      "connections": [
        {
          "target_room": "kitchen",
          "door_entity": "binary_sensor.door_living_kitchen",
          "connection_type": "indoor"           // indoor | outdoor | separate
        }
      ],
      "windows": [
        {
          "entity_id": "binary_sensor.window_living_north",
          "orientation": "north"                  // Calcolato automaticamente
        }
      ]
    }
  ],
  "external_entries": [
    {
      "entity_id": "binary_sensor.front_gate",
      "type": "door",
      "room_side": "garden",
      "orientation": "north",
      "connection_type": "separate"
    }
  ]
}
```

---

### 3.2 Tipologie di aree

| Tipo          | Descrizione                     | `is_outdoor` | `is_separate` | Esempi                     | Comportamento Security               | Comportamento Occupancy |
|---------------|---------------------------------|--------------|---------------|----------------------------|--------------------------------------|--------------------------|
| `indoor`       | Stanza interna standard         | ❌ False      | ❌ False       | Soggiorno, cucina, camera  | Allarme se porta/finestra aperta       | Peso: 1.0                |
| `balcony`      | Balcone o terrazzo              | ✅ True       | ❌ False       | Balcone principale         | Allarme opzionale                     | Peso: 0.5                |
| `garage`       | Garage o box auto                | ❌ False      | ✅ True        | Garage                    | Allarme separato o disabilitato       | Peso: 0.3 (se porta interna aperta) |
| `basement`     | Cantina o seminterrato          | ❌ False      | ✅ True        | Cantina                   | Allarme separato                      | Peso: 0.2                |
| `outdoor`      | Area esterna generica           | ✅ True       | ✅ True        | Giardino, cortile         | Allarme disabilitato                  | Peso: 0.0                |
| `external`     | Esterno (non parte della casa)  | ✅ True       | ✅ True        | Strada, vicinato           | N/A                                   | N/A                      |

---

### 3.3 Connessioni tra aree

| Tipo di connessione | Descrizione                          | Esempio                          | Regole Security                          |
|--------------------|--------------------------------------|----------------------------------|------------------------------------------|
| `indoor`           | Tra 2 stanze interne                 | Cucina → Soggiorno               | Allarme se porta aperta (casa armata)    |
| `outdoor`          | Tra stanza interna e area esterna    | Soggiorno → Balcone              | Allarme opzionale (configurabile)       |
| `separate`         | Tra area separata e esterno         | Garage → Esterno                 | Allarme separato o disabilitato          |

---

### 3.4 Orientamento e coordinate

**Sistema di coordinate**:
- **Origine**: Punto arbitrario (es: angolo in alto a sinistra del floorplan).
- **Unità**: Pixel o unità relative (non metriche reali).
- **Scopo**:
  - Visualizzazione della topologia.
  - Inferenza automatica di connessioni.
  - Calcolo orientamento stanze/finestre.

**Orientamento rispetto al Nord**:
- **Campo globale**: `north_angle` (gradi di rotazione del floorplan rispetto al nord).
  - `0°`: Floorplan allineato al nord (alto = nord).
  - `90°`: Floorplan ruotato di 90° in senso orario (destra = nord).
- **Uso**:
  - Calcolare l’orientamento assoluto di ogni stanza/finestra.
  - Determinare esposizione al sole (es: finestre a sud).

**Formula per calcolare l’orientamento**:
```python
import math

def calculate_orientation(room_coords, house_center, north_angle_degrees):
    dx = house_center[0] - room_coords[0]
    dy = house_center[1] - room_coords[1]
    angle_deg = math.degrees(math.atan2(dy, dx))
    real_angle = (angle_deg - north_angle_degrees) % 360
    
    # Direzioni cardinali
    if 337.5 <= real_angle <= 360 or 0 <= real_angle < 22.5:
        return "north"
    elif 22.5 <= real_angle < 67.5:
        return "northeast"
    elif 67.5 <= real_angle < 112.5:
        return "east"
    elif 112.5 <= real_angle < 157.5:
        return "southeast"
    elif 157.5 <= real_angle < 202.5:
        return "south"
    elif 202.5 <= real_angle < 247.5:
        return "southwest"
    elif 247.5 <= real_angle < 292.5:
        return "west"
    else:
        return "northwest"
```

---

## 4. Inferenza Automatica dalla Configurazione easy-floorplan

### 4.1 Algoritmo per connessioni tra stanze
```python
def find_connecting_rooms(door, areas):
    """
    Trova le 2 stanze collegate da una porta.
    - door: opening dal JSON di easy-floorplan (x, y, length, angle)
    - areas: lista di aree (poligoni con punti)
    """
    # 1. Segmento della porta (inizio e fine)
    door_start = (door["x"], door["y"])
    door_end = (
        door["x"] + door["length"] * math.cos(math.radians(door["angle"])),
        door["y"] + door["length"] * math.sin(math.radians(door["angle"]))
    )
    
    # 2. Trova aree il cui perimetro interseca il segmento della porta
    connecting_areas = []
    for area in areas:
        if line_intersects_polygon(door_start, door_end, area["points"]):
            connecting_areas.append(area["id"])
    
    # 3. Risultato
    if len(connecting_areas) == 2:
        return {
            "room_a": connecting_areas[0],
            "room_b": connecting_areas[1],
            "connection_type": "indoor"
        }
    elif len(connecting_areas) == 1:
        return {
            "room_a": connecting_areas[0],
            "room_b": "outside",
            "connection_type": "outdoor"
        }
    else:
        return None  # Porta non collegata a stanze (es: decorativa)
```

### 4.2 Inferenza di `room_type` e `is_outdoor`
| Campo               | Regola di inferenza                          | Note                          |
|---------------------|---------------------------------------------|-------------------------------|
| `room_type`         | Da `areas[*].name` (es: "Balcone" → `balcony`) | Configurabile manualmente    |
| `is_outdoor`        | `True` se `room_type` in [`balcony`, `outdoor`] | Regola predefinita            |
| `is_separate`       | `True` se `room_type` in [`garage`, `basement`] | Regola predefinita            |
| `connection_type`   | Da `room_type` delle stanze collegate         | Automatico                    |
| `orientation`       | Da `north_angle` + posizione stanza/finestra  | Automatico                    |
| `sun_exposure`      | Da `orientation` + angolo del sole             | Automatico (per finestre)     |

---

## 5. Casi d’Uso e Regole Applicative

### 5.1 Security

| Scenario                              | Condizione                                  | Azione                          |
|---------------------------------------|---------------------------------------------|---------------------------------|
| Porta esterna aperta                  | `connection_type: separate` + casa armata    | Allarme                        |
| Porta balcone aperta                   | `connection_type: outdoor` + casa armata     | Allarme (opzionale)             |
| Porta garage aperta                   | `is_separate: true` + garage armato         | Allarme separato                |
| Finestra cantina aperta               | `is_separate: true` + cantina armata       | Allarme separato                |
| Movimento in giardino                 | `room_type: outdoor`                        | Ignorato (o allarme zone esterne) |

**Esempio di regola**:
```python
if (connection["connection_type"] == "separate" or
    (connection["connection_type"] == "outdoor" and not room["ignore_outdoor_doors"])):
    if door_state == "open" and house_state == "armed_away":
        trigger_alarm()
```

---

### 5.2 Occupancy

**Pesi per tipo di stanza**:
| Tipo stanza     | Peso  | Note                                  |
|-----------------|-------|---------------------------------------|
| `indoor`        | 1.0   | Stanza interna standard               |
| `balcony`       | 0.5   | Presenza pesata meno                 |
| `garage`        | 0.3   | Solo se porta interna aperta            |
| `basement`      | 0.2   | Peso minimo                           |
| `outdoor`       | 0.0   | Ignorato (a meno che configurato)     |

**Formula**:
```python
house_occupancy_score = sum(
    weight * (1 if presence_detected(room) else 0)
    for room, weight in ROOM_WEIGHTS.items()
)
house_state = "home" if house_occupancy_score >= 0.5 else "away"
```

---

### 5.3 HouseState

| Condizione                                      | Stato               |
|-------------------------------------------------|---------------------|
| Tutte porte/finestre esterne chiuse + occupancy ≥ 0.5 | `home`          |
| Qualsiasi porta/finestra esterna aperta         | `home_partial`    |
| Occupancy < 0.5 e porte esterne chiuse          | `away`           |
| Porta garage aperta (occupancy = 0)             | `away_garage_open` |
| Porta cantina aperta (occupancy = 0)             | `away_cellar_open` |

---

### 5.4 Automazioni basate su sole/orientamento

| Orientamento | Automazione                              |
|--------------|-----------------------------------------|
| **Sud**      | Chiudere tapparelle in estate alle 14:00 |
| **Ovest**    | Accendere luce del soggiorno al tramonto   |
| **Nord**     | Nessuna automazione (poca luce diretta)    |
| **Est**      | Aprire tapparelle alle 8:00 in inverno     |

**Esempio**:
```python
for window in room["windows"]:
    if window["orientation"] == "west" and is_sunset_time():
        hass.call_service("cover/close_cover", entity_id=window["entity_id"])
```

---

## 6. Flow di Importazione e Configurazione

### 6.1 Passo 1: Import da easy-floorplan JSON
1. Heima **legge** il file JSON di easy-floorplan (es: `/config/lovelace/easy-floorplan.json`).
2. **Parse** il JSON ed estrae:
   - Stanze (`floors[*].areas`).
   - Porte/finestre (`floors[*].openings`).
   - Muri (`floors[*].walls`).

### 6.2 Passo 2: Inferisce connessioni
- Per ogni **porta** (`opening` con `type: door`), trova le **2 stanze** collegate usando l’algoritmo geometrico.
- Per ogni **finestra** (`opening` con `type: window`), associala alla stanza contenente il muro.

### 6.3 Passo 3: Arricchimento manuale (UI)
L’admin **corregge/arricchisce** i dati tramite UI:
- Imposta `north_angle` (es: slider da 0° a 360°).
- Conferma `room_type` per ogni stanza (dropdown: `indoor`, `balcony`, `garage`, ecc.).
- Flagga porte come **esterne/interne**.
- Aggiunge **pesi** per occupancy (opzionale).

### 6.4 Passo 4: Calcoli automatici
Heima **calcola automaticamente**:
- `orientation` per ogni stanza/finestra (da `north_angle` + posizione).
- `sun_exposure` per ogni stanza (da orientamento + angolo del sole).
- `connection_type` per ogni porta (da `room_type` delle stanze collegate).

### 6.5 Passo 5: Integrazione con i domini
- **Security**: Usa `connection_type` e `room_type` per regole di allarme.
- **Occupancy**: Usa `room_type` e `is_separate` per pesi di presenza.
- **HouseState**: Usa porte esterne + occupancy per stati.
- **Activity**: Usa `orientation` per automazioni sole/luce.

---

## 7. Mockup UI per l’Admin

### 7.1 Schermata 1: Import e Visualizzazione
```
┌─────────────────────────────────────────────────────────────┐
│  [📁 Seleziona file easy-floorplan.json] [Importa]             │
│                                                             │
│  🗺️ Visualizzazione floorplan:                                 │
│  ┌─────────────┬─────────────┐                              │
│  │  Soggiorno   │   Cucina    │                              │
│  │  [□□□□]     │   [□□□□]     │                              │
│  │             │              │                              │
│  └──────┬──────┴──────┬──────┘                              │
│         │ porta       │ porta                               │
│         ▼              ▼                                      │
│  ┌─────────────┐       ┌─────────────┐                       │
│  │  Ingresso    │       │   Balcone    │                       │
│  │  [□□□□]     │       │  [====]      │  ← Terrazzo          │
│  └─────────────┘       └─────────────┘                       │
│                                                             │
│  [N] ← Nord (rotazione: 30°)                                 │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Schermata 2: Configurazione Stanza
```
┌─────────────────────────────────────────────────────────────┐
│  Stanza: Soggiorno (area.living_room)                          │
│ ─────────────────────────────────────────────────────────── │
│  Tipo stanza:        [indoor ▼] (indoor/balcony/garage/...)    │
│  Piano:              [0 ▼] (-1, 0, 1, 2, ...)                   │
│  Area esterna:      ☐ (spuntato = is_outdoor)                 │
│  Area separata:     ☐ (spuntato = is_separate)                │
│  Tipo accesso:      [diretto ▼] (direct/stairs/elevator/...)   │
│                                                             │
│  Connessioni:                                                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Porta → Cucina       [binary_sensor.door_living_kitchen]  ││
│  │   Tipo connessione: [indoor ▼]                           ││
│  │ Porta → Balcone      [binary_sensor.door_living_balcony]││
│  │   Tipo connessione: [outdoor ▼]                          ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  Finestre:                                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Finestra Nord [binary_sensor.window_north]                ││
│  │   Orientamento: [north] (calcolato automaticamente)       ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 7.3 Schermata 3: Configurazione Globale
```
┌─────────────────────────────────────────────────────────────┐
│  Impostazioni topologia globale                                │
│ ─────────────────────────────────────────────────────────── │
│  Angolo rispetto al Nord: [30°] (slider 0-360)               │
│  Centro della casa: (X: [250], Y: [150])                       │
│                                                             │
│  Pesi occupancy:                                              │
│  ┌─────────────────┬─────────────┐                            │
│  │ Stanza indoor    │ 1.0         │                            │
│  │ Balcone          │ [0.5 ▼]     │                            │
│  │ Garage           │ [0.3 ▼]     │                            │
│  │ Cantina          │ [0.2 ▼]     │                            │
│  └─────────────────┴─────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Prossimi Passi

### 8.1 A breve termine (Analisi completata)
- [x] Verificato che Heima **già importa** stanze e dispositivi da HA.
- [x] Identificato **easy-floorplan** come possibile fonte dati (ma solo opzionale, v. §10.2 — non
      più il percorso principale).
- [x] Definito **modello dati** iniziale per stanze, porte, connessioni, orientamento (§3, superato
      da §10).
- [x] Analizzati **casi d'uso** (security, occupancy, house state, automazioni) — restano validi,
      v. §5.
- [x] Review approfondita dal punto di vista admin/resident, verifica overlap con l'architettura
      esistente (`options["rooms"]`, Room Context Model Fase X, `InferenceSignal`, house_state enum
      chiuso) — risultati in §10.

### 8.2 Prossimi passi (Da fare)
1. **Redigere la spec formale della Fase 1** (grafo di topologia, nessuna interfaccia 2D/3D) basata
   su §10.
   - Schema dati dettagliato (`Room` esteso, `Opening`, `Connection`).
   - Integrazione con `options["rooms"]`, `rooms.device_context`, `OccupancyDomain`,
     `_reconcile_rooms()`, Installation Validation (Fase M).
   - Vincoli di prodotto espliciti (privacy, notifiche via AP, explainability via AO).
   - Assegnare la fase nel dev plan (prossima lettera libera dopo AQ).

2. **Validare il modello** con casi reali:
   - Casa con balcone e garage.
   - Casa multi-piano con cantina, vano scale/ascensore con sensori propri.
   - Casa con giardino e ingressi multipli, porta-finestra.

3. **Definire l'editor nel pannello admin** (riuso infrastruttura AO), non un parser di file esterni.

4. **Fase 2 (floorplan visivo)**: non pianificata come fase separata finché non si arriva davvero a
   quel punto — v. §10.1.

---

## 9. Domande Aperte

Stato dopo la review approfondita (§10):

1. ~~**Priorità**: Quale caso d'uso priorizzare?~~ **Risolto**: nessuna priorità tra i tre — sono
   tutti serviti dallo stesso grafo minimo (§10.4-10.5), nessun ordinamento necessario.
2. ~~**Modello dati**: È sufficiente lo schema proposto o manca qualcosa?~~ **Risolto** (con
   correzioni): aggiunti `door_window`, `access_type` su `Connection`, `room_type: transit`; rimossi
   `connection_type`/`is_outdoor`/`is_separate` come campi indipendenti (ora derivati);
   `external_path` assimilato nel grafo. V. §10.3-10.5.
3. ~~**Approccio incrementale**~~ **Risolto**: due fasi nette, v. §10.1. Fase 1 = solo grafo.
4. ~~**Backward compatibility senza easy-floorplan**~~ **Risolto, e ribaltato**: non è più
   "un'opzione di fallback" — è il percorso *principale*. easy-floorplan diventa l'opzionale, solo
   per la Fase 2. V. §10.2.
5. ~~**Performance del calcolo geometrico**~~ **Non più rilevante**: la Fase 1 non fa inferenza
   geometrica delle connessioni — l'admin le dichiara a mano.
6. **Test**: come validare la correttezza della topologia? Ridimensionato: senza inferenza
   automatica, la "correttezza" dipende dall'input dell'admin — diventa principalmente un problema
   di UX/validazione (v. §10.10, integrazione con Installation Validation) più che di test
   algoritmici. Resta aperto **come** integrare esattamente questi controlli in `validation.py`.

Nuove domande emerse dalla review, ancora aperte:

7. `RoomContextSignalProvider` (Fase X, non ancora pubblico) è pensato per segnali booleani/scalari
   per-entità — la topologia è relazionale (grafo), non ci si adatta direttamente. Va bene un
   meccanismo di integrazione separato (namespace `rooms.topology` sibling, non provider), o vale la
   pena riconsiderare l'estensione di quel contratto?
8. Il warning "stesso `entity_id` su più `Opening`" e "stanza isolata nel grafo" in Installation
   Validation: severity `warning` o solo informativo? Deve bloccare il salvataggio in UI o solo
   segnalare?
9. `room_type: transit` — un vano scale/ascensore promosso a `Room` propria: che peso di default per
   l'occupancy? (proposta: basso, analogo a balcone, ma da confermare con un caso reale).

---

## 10. Modello Rivisto (dopo review approfondita)

Questa sezione supersede il modello dati di §§3-4. Le sezioni precedenti restano come riferimento
storico del ragionamento iniziale; questa è la base per la spec formale della Fase 1.

### 10.1 Approccio in due fasi

- **Fase 1 — Grafo di topologia**: nessuna interfaccia 2D/3D. Editor nativo nel pannello admin
  (riuso dell'infrastruttura AO — websocket API, componente frontend). Nessuna dipendenza esterna,
  nessun algoritmo geometrico.
- **Fase 2 — Floorplan visivo** (deferred, non pianificata come fase separata nel dev plan finché
  non ci si arriva davvero): coordinate/poligoni per il rendering. Import opzionale e sostituibile
  da tool esterni (easy-floorplan o altri), mai una dipendenza runtime.

### 10.2 Principio guida: no lock-in su tool di terze parti

easy-floorplan (e qualunque tool analogo) resta **opzionale, solo per la Fase 2**, mai fonte di
verità per il modello dati. Motivo: è un progetto di terze parti con un solo maintainer e un formato
JSON non versionato/garantito, usato solo dal sottoinsieme di utenti che già ha quella specifica card
Lovelace installata. Se sparisce o cambia formato, si rompe solo l'eventuale importer (codice
isolato), mai il modello dati canonico di Heima già persistito.

### 10.3 `Room` — non una nuova entità, estende il registro esistente

Heima ha già un registro canonico per-stanza: `options["rooms"][*]` (`room_inventory.py`,
riconciliato con HA Areas via `_reconcile_rooms()` in `reconciliation.py`). I campi di topologia
sono **aggiunte a quel record esistente**, non una tabella parallela.

Nuovi campi su `Room`:

- `room_type`: `indoor | balcony | garage | basement | outdoor | external | transit`
  - `is_outdoor` / `is_separate` **derivati** da `room_type` via tabella di lookup (§3.2 originale),
    non memorizzati come campi indipendenti — evita drift tra campi ridondanti.
- `floor`: intero (0 = terra, -1 = cantina, 1 = primo piano, ...).
- `exposure`: **derivato** dall'unione degli `orientation` dei suoi `Opening` — non dichiarato
  indipendentemente (decisione presa in discussione).
- `geometry: null` — hook esplicitamente riservato per la Fase 2, stesso pattern già in uso per
  `Activity.context: dict[str, Any]` (architecture non-negotiable #12): dichiarato ora, popolato
  solo quando la Fase 2 esiste, zero migrazione quando arriva.

`room_type: transit` è per spazi (vano scale, cabina ascensore) **promossi** a `Room` propria solo
quando hanno sensori/attuatori da agganciare (rilevatore di movimento, luce del vano, pulsantiera).
Se non hanno sensori, restano solo un attributo di `Connection` (§10.5) — nessuna promozione
necessaria. Peso di occupancy basso (presenza transitoria), da tarare con un caso reale (v. domanda
aperta #9).

### 10.4 `Opening` — porte e finestre

Struttura nuova (non esiste equivalente oggi):

- `opening_id`, `room_id`, `type: door | window | door_window`, `orientation` (cardinale, dichiarato
  a mano — mai calcolato geometricamente), `entity_id: string | None`.
- `entity_id` **esplicitamente opzionale**: copre porte/finestre senza sensore, che restano utili
  come riferimento geografico puro per usi futuri (es. notifiche ambientali tipo "chiudi la
  finestra, c'è vento" — non costruite ora, ma il modello dati non deve bloccarle dopo).
- Lo stesso `entity_id` **può** essere referenziato da più `Opening`: casi reali sono sensori
  d'allarme cablati in serie/parallelo su più finestre fisiche, o la porta-finestra (v. sotto). Non
  è un errore di validazione — al massimo un warning morbido e non bloccante in Installation
  Validation.
- `door_window` (porta-finestra) si comporta sia da `door` (genera una `Connection`) sia da `window`
  (ha `orientation`, contribuisce a `exposure`) — un solo record invece di duplicare l'entity su due
  `Opening` separati. Modella un caso molto comune nelle case italiane.

### 10.5 `Connection` — solo collegamenti room-to-room

- Collega due `Room` (o `Room` ↔ esterno/separato) tramite un `Opening` di tipo `door`/`door_window`.
- `connection_type: indoor | outdoor | separate` — **derivato** dai `room_type` dei due estremi
  (tabella §3.3 originale), con override opzionale solo per casi anomali.
- `access_type: direct | stairs | elevator` — campo nuovo, spostato da `Room` (dov'era nel modello
  originale) a `Connection`: descrive *come* si attraversa quella specifica connessione, non una
  proprietà della stanza (la stessa stanza può avere più connessioni con `access_type` diversi).
  Collega naturalmente `Room` con `floor` diverso.
- `external_path` **non esiste più come valore**: assimilato modellando lo spazio intermedio
  (vialetto, giardino, terrazzo) come `Room(room_type=outdoor)` — il percorso esterno è
  rappresentato dal grafo stesso, non da un flag.

### 10.6 Integrazione architetturale — più semplice del previsto

A differenza del recovery state (ricalcolato ogni ciclo, richiede un'"Architecture Integration"
dedicata come in `runtime_checkpoint_and_power_recovery_spec.md`), la topologia è quasi statica:
cambia solo quando l'admin la edita.

Precedente diretto già in produzione: **Room Context Model (Fase X, `DONE`)** — preprocessing layer
esplicitamente *non* un dominio DAG, che scrive `CanonicalState["rooms.device_context"]` prima della
risoluzione di house-state.

La topologia segue lo stesso pattern: namespace fratello `rooms.topology`, calcolato una volta
all'avvio/su cambio configurazione e cacheato (non ricalcolato ogni ciclo), letto dai domini che ne
hanno bisogno (Security, Occupancy, HouseState) come dato di configurazione, non come segnale
per-ciclo.

### 10.7 Occupancy — non un `InferenceSignal` (autocorrezione)

Il peso di occupancy per tipo-stanza **non** è un `InferenceSignal` (`inference/signals.py`: quel
contratto ha `confidence`/`ttl_s`, pensato per predizioni probabilistiche con decadimento — non si
adatta a un fatto statico configurato). È invece un parametro letto direttamente da
`OccupancyDomain`, accanto a `room_occupancy_mode` che già esiste lì.

### 10.8 HouseState — enum chiuso, nessuna estensione

Nessun nuovo stato top-level (niente `away_garage_open`/`away_cellar_open`). Fatti come "garage
aperto" restano context/diagnostics ausiliari, non nuovi valori dell'enum `house_state`.

### 10.9 Vincoli di prodotto (da scrivere esplicitamente nella spec formale)

- **Privacy**: topologia e (futura) visualizzazione floorplan restano a livello di stanza-aggregata
  (`occupied: bool`), mai per-persona — coerente con la scelta già documentata di non fare
  apprendimento per-persona. Da scrivere esplicitamente ora, prima che la Fase 2 renda la tentazione
  concreta.
- **Notifiche**: qualunque notifica futura derivata da topologia deve passare dalla Notification
  Delivery Policy (AP) esistente — family/audience/soglie/burst limit — mai un canale ad hoc.
- **Explainability**: le decisioni guidate da topologia (blocchi/permessi Security) devono comparire
  nei decision trace già esposti da AO, non diventare una nuova fonte silenziosa di "perché non ha
  funzionato".
- **Editing**: admin-only, coerente con AO/AP.

### 10.10 Reconciliation e validazione

- Se un'HA Area viene rinominata/eliminata: `Opening`/`Connection` orfane vanno segnalate
  esplicitamente (warning), non cancellate silenziosamente — hook nello stesso ciclo di vita di
  `_reconcile_rooms()`.
- Se un `entity_id` referenziato da un `Opening` sparisce dall'Entity Registry: marcato
  `entity_unavailable`, non silenziosamente perso.
- Completezza della configurazione (stanze senza `Opening`, stanze `indoor` isolate nel grafo)
  integrata nel framework di Installation Validation esistente (Fase M, `validation.py`) come nuova
  `ValidationSection`, non un indicatore bespoke.

### 10.11 Numerazione nel dev plan

Nuova fase, prossima lettera libera dopo AQ. La Fase 2 (floorplan/geometria) non viene
pre-registrata come fase separata finché non ci si arriva davvero — coerente con "non pianificare a
vuoto".

---

## 11. Riferimenti

- [easy-floorplan GitHub](https://github.com/nicosandller/easy-floorplan)
- [Home Assistant Area Registry Docs](https://developers.home-assistant.io/docs/area_registry_index/)
- [ha-floorplan (alternativa)](https://github.com/ExperienceLovelace/ha-floorplan)
- Heima `reconciliation.py`: [link locale](file:///Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/custom_components/heima/reconciliation.py)
- Heima `discovery.py`: [link locale](file:///Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/custom_components/heima/discovery.py)
