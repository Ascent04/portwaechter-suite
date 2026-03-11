# MONTHLY_REVIEW_RUNBOOK

Stand: 2026-03-11
Aktiver Produktivpfad: `/opt/portwaechter`

## Monatspruefung

1. Monatsstand im Operator-View ziehen:
   - Telegram: `/organism`
   - Telegram: `/execution`
   - Telegram: `/portfolio`
2. Falls ein frischer Monatsreport geschrieben werden soll:
   ```bash
   cd /opt/portwaechter
   ./.venv/bin/python -c "from modules.common.config import load_config; from modules.organism.report_render import build_and_write_monthly_evaluation; print(build_and_write_monthly_evaluation(load_config()))"
   ```
3. Report-Datei pruefen:
   - `data/organism/monthly/monthly_evaluation_YYYY_MM.json`

## Welche Kennzahlen pruefen

- `executed_entries_count`
- `realized_exit_count`
- `closed_total`
- `partial_exits_total`
- `realized_pnl_before_costs`
- `realized_pnl_minus_cost_eur`
- `cost_coverage_status`
- `realized_pnl_complete`
- `unrealized_pnl_eur_total`
- `open_positions_total`
- `partially_closed_total`
- `largest_open_position_eur`
- `largest_open_risk_eur`

Quellen im Code:

- `modules/virus_bridge/execution_report.py`
- `modules/virus_bridge/cost_status.py`
- `modules/organism/monthly_evaluation.py`
- `modules/organism/report_render.py`

## Kostenstatus

1. Immer `realized_pnl_minus_cost_eur` gegen `monthly_cost_usd = 30` lesen.
2. Diese Statuswerte gelten:
   - `NOCH_NICHT_BEWERTBAR`
   - `NICHT_GEDECKT`
   - `NAHE_BREAK_EVEN`
   - `KOSTEN_GEDECKT`
3. Ein Monat ohne echte Ausfuehrungen oder ohne belastbare Exits ist nicht wirtschaftlich bewertbar.

## Reale Ausfuehrungen

1. `executed_entries_count` muss groesser als null sein, sonst keine operative Fortschrittsaussage.
2. `realized_exit_count` zeigt, wie viele Exits fuer die Real-Performance wirklich verwertbar sind.
3. Nur manuell erfasste Executions und Exits zaehlen.

## Geschlossene Trades

1. `closed_total` gegen `/execution` pruefen.
2. Bei mehreren Exit-Teilen nur gewichtete Exit-Auswertung akzeptieren.
3. Wenn `realized_pnl_complete == false`, Monatsfazit defensiv halten.

## Offene Restpositionen

1. `open_positions_total` und `partially_closed_total` pruefen.
2. `unrealized_pnl_eur_total` nur als Nebenlage lesen, nicht als Kosten-Deckung.
3. Grosse Restpositionen mit hohem `largest_open_risk_eur` bremsen den Ausbau.

## Organism- / Monatsbewertung

1. `/organism` ist die kompakte Operator-Sicht.
2. Die Bewertungslogik kommt aus `evaluate_organism()` in `modules/organism/monthly_evaluation.py`.
3. Relevante Zielzustande im aktuellen Pfad:
   - `UEBERPRUEFEN`
   - `GEDROSSELT_FUEHREN`
   - `WEITER_FUEHREN`
   - `AUSBAUEN`

## Wann Wachstum gerechtfertigt ist

Wachstum ist nur gerechtfertigt, wenn alle Punkte gleichzeitig sauber sind:

- echte Ausfuehrungen vorhanden
- belastbare geschlossene Trades vorhanden
- `realized_pnl_complete == true`
- `cost_coverage_status == KOSTEN_GEDECKT`
- `realized_pnl_minus_cost_eur > 0`
- keine sichtbare API-Stresslage als Dauerzustand

## Wann Risiko gesenkt werden soll

Risiko senken oder den Desk gedrosselt fuehren, wenn einer dieser Punkte zutrifft:

- `executed_entries_count == 0`
- `cost_coverage_status` ist `NICHT_GEDECKT`
- `realized_pnl_minus_cost_eur < 0`
- `realized_pnl_complete == false`
- hohe offene Restpositionen bei schwacher Monatswirkung
- `/execution` oder `/portfolio` zeigen wiederholt Warnlagen

## Monatsabschluss

1. `/execution` und `/organism` muessen fachlich dieselbe Aussage tragen.
2. Den Monatsreport unter `data/organism/monthly/` ablegen und nicht ueberschreiben.
3. Keine Expansion aus Signalmenge ableiten. Nur echte, nach Kosten belastbare Wirkung zaehlt.
