API Governor

Ziel
- Twelve Data innerhalb eines festen Minuten- und Laufbudgets halten.
- Holdings immer zuerst bedienen.
- Scanner-Werte rotieren statt in jedem Lauf alles neu abzufragen.
- Bei Budgetdruck kontrolliert degradieren statt weiter Requests zu feuern.

Kernlogik
- `minute_limit_soft`: Warnzone. Ab hier geht der Scanner in den Modus `degraded`.
- `minute_limit_hard`: Harte Minutegrenze. Neue Twelve-Data-Requests werden blockiert.
- `per_run_budget`: Maximale Twelve-Data-Requestzahl pro V2-Lauf.
- `batch_only`: Scannerbetrieb darf nur Batch-Abfragen nutzen.
- `allow_symbol_search_runtime=false`: Symbolsuche ist im Live-Betrieb gesperrt.

Holdings First
- Holdings werden vor allen Scanner-Werten abgearbeitet.
- Scanner-Werte werden in `scanner_high` und `scanner_low` geteilt.
- Bei aktivierter Rotation nimmt jeder Lauf einen anderen Scanner-Chunk.

Degrade Mode
- `normal`: Holdings plus Scanner-Chunk.
- `degraded`: Holdings zuerst, Scanner werden stark reduziert oder ganz gestrichen.
- `blocked`: Keine neuen Twelve-Data-Calls mehr. Es bleiben nur lokale oder gecachte Daten.

Batch-Only Policy
- `fetch_quotes_for_instruments()` arbeitet im Scannerpfad nur in Batches.
- Einzel-Retries fuer Holdings sind nur erlaubt, wenn `batch_only=false`.
- Manuelle Einzelpruefungen wie Ticket-Details koennen weiter `get_quote()` nutzen.

State und Metriken
- State: `data/api_governor/state.json`
- Usage Log: `data/api_governor/usage_YYYYMMDD.jsonl`
- Jede Batch-Abfrage schreibt ein JSONL-Event ohne Secrets.

Run Summary
- Jeder V2-Lauf schreibt eine sichtbare Summary:
- `v2_governor_summary: selected_assets=... holdings_count=... scanner_count=... api_cost=... minute_used=... mode=...`

V1/V2 Collision Avoidance
- V2 ist der primaere Twelve-Data-Pfad.
- V1 `marketdata_watcher` bleibt auf dem bestehenden Stooq-/Fallback-Pfad.
- Damit entsteht keine doppelte Twelve-Data-Last fuer denselben Zyklus.

Beispiele
- `normal`: 12 Holdings + 18 Scanner, `api_cost=4`
- `degraded`: 12 Holdings + 4 Scanner, `api_cost=2`
- `blocked`: 12 Holdings, `api_cost=0`, nur Cache/Fallback
