# Heima — Options Flow UX v2 SPEC

**Status:** In progress — branch `main`
**Created:** 2026-03-17

---

## Motivazione

Il config flow v1 presentava tre problemi principali:

1. **Nessuna visibilità della configurazione attuale** nei menù: l'utente non sapeva cosa fosse configurato senza entrare in ogni sotto-step.
2. **UX confusa per la heating vacation curve**: selettore del tipo di branch e parametri nello stesso form — cambiare il tipo richiedeva un submit intermedio per aggiornare i campi visibili.
3. **Reactions menu silenziosamente vuoto**: dopo aver accettato una proposta nel config flow ma prima di salvare, il menu Reazioni risultava vuoto perché `_get_registered_reaction_ids` leggeva solo l'engine post-save, non la sessione corrente.

---

## Decisioni implementate

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

**Implementazione:** metodo `_init_status_block() -> str` in `HeimaOptionsFlowHandler`.

### D2 — Configuration summary nei menù di secondo livello

Ogni menù di secondo livello mostra un riassunto della configurazione attuale tramite `description_placeholders`.

| Menù | Placeholder | Esempio |
|------|-------------|---------|
| `people_menu` | `summary` | `Configurate: 3: Stefano, Elena, Marco` |
| `rooms_menu` | `summary` | `Configurate: 4: Soggiorno, Cucina, Studio, Camera` |
| `lighting_rooms_menu` | `summary` | `Scene configurate: 3/4 stanze` |
| `heating_branches_menu` | `summary` | `climate.termostato \| 2 branch` |

**Implementazione:** helper `_people_menu_summary()`, `_rooms_menu_summary()`, `_lighting_menu_summary()`, `_heating_menu_summary()` in `HeimaOptionsFlowHandler`.

> **Stato:** D1 e D2 implementati. Le label stanno nelle traduzioni (`init.description`), i valori vengono dai mixin. `_init_status_block()` è orchestratore puro e localizza i valori booleani via `CONF_LANGUAGE`.

### D3 — Heating branch: flusso in due step

Il flusso di configurazione di un heating branch override è stato suddiviso:

1. `heating_branch_select` — mostra solo il selettore del tipo di branch (`vacation_curve`, `fixed_temp`, `disabled`)
2. `heating_branch_edit_form` — mostra solo i parametri specifici del tipo selezionato (no branch selector)

Se il branch selezionato è `disabled`, il form parametri viene saltato e si torna direttamente al menù.

### D4 — Reactions: merge engine + sessione corrente

`_get_registered_reaction_labels()` (già `_get_registered_reaction_ids`) ora:
1. Aggrega le reaction dall'engine in esecuzione e dalla sessione corrente (proposte accettate non ancora salvate)
2. Restituisce `dict[str, str]` — `{reaction_id: label}` — per la `multi_select` del form "Reazioni silenziose"
3. La label viene salvata in `reactions["labels"][pid]` al momento dell'accettazione della proposta

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

**Session state:** `_pending_action_configs: list[str]` — coda di proposal ID da configurare. Viene popolata in `async_step_proposals` e consumata uno alla volta da `async_step_proposal_configure_action`.

**Storage:** `configured[pid]["steps"]` e `configured[pid]["pre_condition_min"]` vengono aggiornati in-place prima di chiamare `_update_options`.

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

---

## File modificati

- `custom_components/heima/const.py` — `STRUCTURAL_OPTION_KEYS`
- `custom_components/heima/__init__.py` — selective reload in `_async_entry_updated`
- `custom_components/heima/coordinator.py` — `last_options_snapshot`
- `custom_components/heima/config_flow/__init__.py` — `_update_options`, `_init_status_block`, summary helpers
- `custom_components/heima/config_flow/_steps_general.py`
- `custom_components/heima/config_flow/_steps_heating.py`
- `custom_components/heima/config_flow/_steps_security.py`
- `custom_components/heima/config_flow/_steps_calendar.py`
- `custom_components/heima/config_flow/_steps_notifications.py`
- `custom_components/heima/config_flow/_steps_reactions.py` — D4, D5
- `custom_components/heima/config_flow/_steps_people.py`
- `custom_components/heima/config_flow/_steps_rooms.py`
- `custom_components/heima/config_flow/_steps_lighting.py`
- `custom_components/heima/translations/it.json`
- `custom_components/heima/translations/en.json`
