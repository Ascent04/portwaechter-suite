## Audit / Lifecycle

Der CB Fund Desk speichert fuer jedes Ticket einen rekonstruktionsfaehigen Lebenszyklus und koppelt jeden wesentlichen Schritt an die bestehende Audit-Logik an.

### Ziel

- Jeder Trade-Kandidat bleibt vom Erstellen bis zum Exit nachvollziehbar.
- Manuelle Ausfuehrungen, Teilverkaeufe, Komplettverkaeufe, Ablehnungen und Verschiebungen werden als Lifecycle-Ereignisse festgehalten.
- Wenn die offizielle Audit-Kette verfuegbar ist, wird sie genutzt. Nur bei Ausfall wird auf eine append-only JSONL-Datei im `virus_bridge`-Pfad ausgewichen.

### Eventtypen

- `TRADE_CANDIDATE_CREATED`
- `TRADE_TICKET_SENT`
- `TRADE_EXECUTED_MANUAL`
- `TRADE_REJECTED_MANUAL`
- `TRADE_DEFERRED`
- `TRADE_PARTIAL_EXIT`
- `TRADE_CLOSED_MANUAL`
- `TRADE_CLOSED_STOP_LOSS`
- `TRADE_CLOSED_TARGET_REACHED`

### Statusmodell

- `CREATED`
- `SENT`
- `OPEN`
- `EXECUTED`
- `PARTIALLY_CLOSED`
- `CLOSED`
- `REJECTED`
- `DEFERRED`

Der aktuelle Status wird aus dem letzten gueltigen Lifecycle-Ereignis abgeleitet. Bei Konflikten zwischen `ticket_state.json` und Lifecycle-Datei wird Lifecycle bevorzugt und intern geloggt.

### Dateipfade

- Lifecycle: `data/virus_bridge/ticket_lifecycle/<ticket_id>.json`
- Fallback-Audit: `data/virus_bridge/audit_events_YYYYMMDD.jsonl`
- Ticket-Status: `data/virus_bridge/ticket_state.json`
- Manuelle Ausfuehrungen: `data/virus_bridge/executions/YYYYMMDD/`
- Exits: `data/virus_bridge/exits/YYYYMMDD/`

### Beispiel-Lifecycle

1. `TRADE_CANDIDATE_CREATED`
2. `TRADE_TICKET_SENT`
3. `TRADE_EXECUTED_MANUAL`
4. `TRADE_PARTIAL_EXIT`
5. `TRADE_CLOSED_TARGET_REACHED`

Damit ist ein Trade vom Ticket bis zum finalen Exit ohne Broker-Anbindung rekonstruierbar.

### Validierungslogik

Die Lifecycle-Validierung prueft unter anderem:

- Erstellungsereignis vorhanden
- kein `EXECUTED` ohne vorheriges `CREATED` oder `SENT`
- kein `CLOSED` ohne `EXECUTED`
- keine doppelten terminalen Close-Events
- Restgroesse konsistent zu Teilverkaeufen, soweit aus `ticket_state.json` ableitbar

### Fallback-Verhalten

Wenn das offizielle Audit-Backend nicht importierbar ist oder beim Schreiben fehlschlaegt, werden Audit-Ereignisse append-only in `data/virus_bridge/audit_events_YYYYMMDD.jsonl` geschrieben. Secrets oder Tokens werden dabei nicht geloggt.
