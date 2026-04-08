# Heima — Claude Code Instructions

## Project
Intent-driven home intelligence engine as Home Assistant custom integration.
GitHub org: Heima Labs. Repo: `ha-heima-component`.

## Language
Respond in Italian unless code, identifiers, or spec content requires English.

## Communication style
- Risposte stringate. Dettagli solo se richiesti esplicitamente.
- Per scelte architetturali: breve discussione prima di toccare il codice.

## Commit style
- Messaggi brevi: titolo imperativo + 2-3 righe di contesto max.
- Non committare mai senza richiesta esplicita dell'utente.
- Aggiungere sempre `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`.

## Branch model
- `main` è il branch di produzione. Si fa merge solo quando la feature/fix è completa.
- Il lavoro avviene su branch dedicati (es. `feat/...`, `fix/...`).
- Non committare direttamente su `main` a meno che non sia un fix banale o documentazione.

## Code rules
- Nessun backward compatibility: unico utente del progetto.
- No ML libraries nei built-in. Pure Python + statistics stdlib. Il core resta dependency-free.
- Tutti i test devono essere verdi dopo ogni modifica.
- Test count attuale: 660. Non rompere test esistenti senza motivo esplicito.
- Prima di modificare un file: leggerlo.

## Architecture invariants
- Il DAG di valutazione è: InputNormalizer → People → Occupancy → Calendar → HouseState → Lighting → Heating → Security → Apply.
- I domini leggono CanonicalState (ciclo precedente), NON gli output degli altri domini nel ciclo corrente.
- Nessuna dipendenza circolare tra domini.
- Apply plan è l'unico canale di output per le azioni su HA.

## Decisioni architetturali prese

### Multi-persona
v1 apprende pattern a livello household, non per persona. È una limitazione nota e documentata,
non un bug. Per-person learning è pianificato per v2, non schedulato.

### Inference Engine v2
La spec esiste in `docs/specs/learning/inference_engine_spec.md` ma l'implementazione è 0%.
Stato: RFC/on-hold. Non schedulare lavoro su v2 inference senza decisione esplicita dell'utente.

### Plugin API
In v1 i registry sono built-in. Il caricamento dinamico di plugin di terze parti non è supportato.
Chi vuole aggiungere un plugin deve modificare `registry.py`. Questo è by design fino a v2.

## Key specs
- v1: `docs/specs/rfc/heima_spec_v1.md`
- v2: `docs/specs/heima_v2_spec.md`
- Learning system: `docs/specs/learning/learning_system_spec.md`
- Spec index: `docs/specs/INDEX.md`

## Auditing e debug
- Per diagnostics runtime: `python3 scripts/diagnostics.py --section <engine|plugins|event_store>`
- Per learning audit: `python3 scripts/learning_audit.py --ha-url $HA_URL --ha-token $HA_TOKEN`
- Per review longitudinale: `ops_audit.py --snapshot-out` + `--compare-to`
- Portare a Claude il JSON di output, non chiedere di inferire lo stato dal codice.
