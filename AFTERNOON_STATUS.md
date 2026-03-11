# AFTERNOON_STATUS

Stand: 2026-03-11
Aktiver Produktivpfad: `/opt/portwaechter`

## 1. Erledigter Stand

Der aktive Desk-Pfad in `/opt/portwaechter` ist fachlich als kleiner manueller Fund-Desk zusammengezogen:

- V2-Signale laufen ueber `SignalProposal` in die file-basierte Bridge-Queue.
- Die Virus Bridge bewertet TR-Verifikation, Marktstatus, Datenfrische, Stop, Risiko und Groesse.
- Buy-Signale ohne operative Pflichtfelder werden nicht mehr wie fertige Tickets behandelt.
- Teilverkaeufe, Vollschliessungen, Stop-Loss und Ziel-erreicht-Exits laufen ueber einen manuellen Telegram-Workflow.
- Execution-, Partial-Exit- und Closed-Trade-Auswertung sind auf eine einheitliche Desk-Wahrheit ausgerichtet.
- `/execution` und `/organism` sind an denselben Kosten- und Performance-Kern gekoppelt.
- Der Kostenbezug von `30 USD` pro Monat ist im aktiven Code hinterlegt.
- Betriebs- und Uebergabedoku ist angelegt:
  - `SYSTEM_OVERVIEW.md`
  - `NIGHTLY_HANDOFF.md`
  - `DAILY_DESK_RUNBOOK.md`
  - `MONTHLY_REVIEW_RUNBOOK.md`
  - `DECISION_REPO_STRATEGY.md`

## 2. Geaenderte Kernmodule

Kernbereiche, die den aktuellen Stand tragen:

- `modules/virus_bridge/execution_performance.py`
- `modules/virus_bridge/execution_report.py`
- `modules/virus_bridge/exit_flow.py`
- `modules/virus_bridge/execution_workflow.py`
- `modules/virus_bridge/stop_loss.py`
- `modules/virus_bridge/risk_eval.py`
- `modules/virus_bridge/cost_status.py`
- `modules/common/operator_signals.py`
- `modules/organism/monthly_evaluation.py`
- `modules/organism/report_render.py`
- `modules/portfolio_status/status.py`
- `modules/telegram_commands/poller.py`
- `modules/telegram_commands/handlers.py`
- `modules/telegram_commands/ui.py`
- `modules/integration/pw_to_virus.py`
- `modules/virus_bridge/main.py`

## 3. Testergebnisse

Heute bestaetigt oder dokumentiert gruen:

- Nachtblock laut `NIGHTLY_HANDOFF.md`:
  - Telegram-, Portfolio-, Execution- und Help-Block: `21 passed`
  - angrenzende Execution-/Ticket-Tests: `4 passed`
  - Keyboard- und UI-Layout-Tests: `4 passed`
  - Nachtgesamt: `29 passed`
- Heutige Schwellen-/Risk-/Stop-/Trade-Candidate-Suite:
  - `tests/test_virus_bridge_risk_eval.py`
  - `tests/test_stop_loss.py`
  - `tests/test_virus_bridge_trade_candidate.py`
  - `tests/test_trade_ticket_risk_fields.py`
  - `tests/test_virus_bridge_budget.py`
  - `tests/test_data_quality.py`
  - Ergebnis: `30 passed`
- Heutige Operator-/Render-Suite:
  - `tests/test_ticket_market_open_render.py`
  - `tests/test_incomplete_buy_ticket_delivery.py`
  - `tests/test_buy_message_operational.py`
  - `tests/test_v2_render.py`
  - Ergebnis: `9 passed`
- Heutige Bridge-/Smoke-Suite:
  - `tests/test_virus_bridge_main_smoke.py`
  - `tests/test_virus_bridge_entry_stop.py`
  - `tests/test_trade_ticket_risk_fields.py`
  - `tests/test_incomplete_buy_ticket_delivery.py`
  - Ergebnis: `7 passed`
- Finaler Risk-/Render-Recheck:
  - `tests/test_virus_bridge_risk_eval.py`
  - `tests/test_stop_loss.py`
  - `tests/test_virus_bridge_trade_candidate.py`
  - `tests/test_ticket_market_open_render.py`
  - `tests/test_incomplete_buy_ticket_delivery.py`
  - Ergebnis: `30 passed`

Faktischer Datenstand im Arbeitsverzeichnis:

- `data/virus_bridge/executions/`: `0` Dateien
- `data/virus_bridge/exits/`: `0` Dateien
- `data/virus_bridge/ticket_lifecycle/`: `39` Dateien
- `data/virus_bridge/trade_candidates/`: `54` Dateien
- `data/integration/signal_proposals/`: `69` Dateien
- `data/organism/monthly/`: `1` Monatsreport

## 4. Operative Verbesserungen

- Telegram-Signale sind strenger operatorisch getrennt in operativ nutzbar vs. unvollstaendig.
- Markt geschlossen, stale Quotes und reduzierte Ticket-Reife wirken nicht mehr wie normale Kauf-Tickets.
- Stop-Loss ist strukturbasiert, wenn ein plausibler Strukturanker vorliegt, sonst klarer Fallback.
- Risiko pro Trade wird gegen das Desk-Budget durchgesetzt.
- Exit-Workflow erfasst Teilverkauf, Vollverkauf, Stop-Loss und Ziel erreicht mit sauberer Validierung.
- `/execution` kann offene, teilweise geschlossene und geschlossene Tickets fachlich getrennt darstellen.
- Leere Betriebsordner und Erstbetrieb werden defensiv behandelt.

## 5. Restrisiken

- Es gibt im aktuellen Datenstand noch keine echten `execution_*.json`- oder `exit_*.json`-Dateien. Der reale Trade-Pfad ist deshalb code- und testseitig gehaertet, aber noch nicht mit echtem Trade-Material belegt.
- Offene PnL bleibt weiterhin von belastbaren aktuellen Quotes abhaengig.
- Struktur-Stops greifen nur, wenn explizite Strukturanker im aktiven Datenpfad vorliegen.
- Keine Broker- oder Depot-API zur automatischen Gegenpruefung von Executions und Exits.
- Das separate Repo `/home/ascent/cb-virus-fund` ist technisch stark, aber nicht der aktive Betriebsstrang. Eine Parallelpflege wuerde doppelte Scanner-, Risk-, Telegram- und PnL-Welten erzeugen.
- Der vorhandene Monatsreport `data/organism/monthly/monthly_evaluation_2026_03.json` wurde am `2026-03-10T19:22:53+01:00` geschrieben und zeigt noch `monthly_cost_usd = 29.0`. Die aktive Konfiguration steht inzwischen auf `30 USD` und braucht fuer die aktuelle Sicht einen neuen Monatslauf.

## 6. Naechste 3 Prioritaeten

1. Einen ersten echten manuellen Trade im aktiven Pfad vollstaendig durchlaufen:
   Kauf -> Teilverkauf oder Vollverkauf -> `/execution` -> `/organism`
2. Die aktuellen Reports neu schreiben:
   - frischen Execution-Report erzeugen
   - Monatsreport unter der `30 USD`-Referenz neu erzeugen
3. Erst nach echtem Realbetrieb entscheiden, ob einzelne Hardenings aus `/home/ascent/cb-virus-fund` uebernommen werden:
   - Audit-Hashkette
   - Selfcheck / Heartbeat
   - Config-Snapshot / Fingerprint

## 7. Ehrliches Gesamturteil

### Technisch

Der aktive Pfad ist als V1 konsistent. Die Kernlogik fuer Signalreife, Risiko, Lifecycle, Exit-Auswertung, Execution-Sicht, Monatsbewertung und Telegram-Operatorfluss ist im Code vorhanden und gegen Grenzfaelle getestet.

### Operativ

Der Desk ist fuer den ersten echten Human-in-the-loop-Trade vorbereitet. Leere und unvollstaendige Zustaende werden defensiv behandelt. Die eigentliche Feldbestaetigung im Realbetrieb fehlt aber noch, weil im aktuellen Datenstand keine echten Executions und Exits vorliegen.

### Wirtschaftlich

Wirtschaftlicher Fortschritt ist aktuell nicht nachgewiesen. Der letzte gespeicherte Monatsreport zeigt:

- `executed_total = 0`
- `closed_total = 0`
- `realized_pnl_eur_total = 0`
- `organism_status = UEBERPRUEFEN`

Damit ist der Desk technisch deutlich weiter als wirtschaftlich belegt.
