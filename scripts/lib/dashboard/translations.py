# lib/dashboard/translations.py
from typing import Dict

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "it": {
        # Titoli delle sezioni
        "Runtime": "Runtime",
        "Learning And Events": "Apprendimento ed Eventi",
        "Runtime Reactions": "Reazioni Runtime",
        "Test Lab": "Laboratorio di Test",
        "Developer Actions": "Azioni Sviluppatore",
        "All Heima Entities": "Tutte le Entità Heima",
        # Titoli delle card
        "Runtime Diagnostics": "Diagnostica Sistema",
        "Core Runtime Entities": "Entità Runtime Principali",
        "Runtime Trend": "Andamento Runtime",
        "Occupancy And People": "Presenza e Persone",
        "Learning, Events, Proposals": "Apprendimento, Eventi, Proposte",
        "Anomalies And Alerts": "Anomalie e Allarmi",
        "Heating": "Riscaldamento",
        "Security": "Sicurezza",
        "Active Runtime Reactions": "Reazioni Runtime Attive",
        "Configured Reactions": "Reazioni Configurate",
        "Lighting Runtime": "Runtime Illuminazione",
        "Uncategorized Heima Entities": "Entità Heima Non Categorizzate",
        # Etichette
        "House State": "Stato Casa",
        "Anyone Home": "Presenza in Casa",
        "People Count": "Numero Persone",
        "Security State": "Stato Sicurezza",
        "Room": "Stanza",
        "Display": "Nome Visualizzato",
        "Area": "Area",
        "Occupancy mode": "Modalità Presenza",
        "Discovered entities": "Entità Rilevate",
        "Configured reactions": "Reazioni Configurate",
        "Reaction": "Reazione",
        "Enabled": "Attiva",
        "Source": "Sorgente",
        "Fire": "Attivazioni",
        "Suppressed": "Soppressioni",
        "State": "Stato",
        # Snapshot fields
        "house_state": "Stato Casa",
        "anyone_home": "Presenza in Casa",
        "people_count": "Numero Persone",
        "occupied_rooms": "Stanze Occupate",
        "security_state": "Stato Sicurezza",
        "notes": "Note",
        # Azioni
        "Recompute Now": "Ricalcola Ora",
        "Reload Heima Entry": "Ricarica Configurazione Heima",
        "Reset Test Lab": "Reimposta Laboratorio di Test",
    },
    "en": {
        # Default: stesso testo originale
        "Runtime": "Runtime",
        "Learning And Events": "Learning And Events",
        # ... (copia dei test originali)
    },
}

def translate(key: str, lang: str = "it") -> str:
    """Traduce una chiave nella lingua specificata."""
    return TRANSLATIONS.get(lang, {}).get(key, key)