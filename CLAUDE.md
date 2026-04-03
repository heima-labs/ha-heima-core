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

## Code rules
- Nessun backward compatibility: unico utente del progetto.
- No ML libraries nei built-in. Pure Python + statistics stdlib.
- Tutti i test devono essere verdi dopo ogni modifica.
- Test count attuale: 314. Non rompere test esistenti senza motivo esplicito.
- Prima di modificare un file: leggerlo.

## Architecture invariants
- Il DAG di valutazione è: InputNormalizer → People → Occupancy → HouseState → Lighting → Heating → Security → Apply.
- I domini leggono CanonicalState (ciclo precedente), NON gli output degli altri domini nel ciclo corrente.
- Nessuna dipendenza circolare tra domini.
- Apply plan è l'unico canale di output per le azioni su HA.

## Key specs
- v1: `docs/specs/rfc/heima_spec_v1.md`
- v2: `docs/specs/heima_v2_spec.md`
- Learning system: `docs/specs/learning/learning_system_spec.md`
