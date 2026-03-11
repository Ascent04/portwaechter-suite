# 15UHR_STATUS

Stand: 2026-03-11
Aktiver Produktivpfad: `/opt/portwaechter`

## 1. Heute umgesetzt

- Closed-Trade- und Partial-Exit-Auswertung fachlich gehaertet:
  - gewichteter Exit-Durchschnitt
  - saubere Trennung `OPEN` / `PARTIALLY_CLOSED` / `CLOSED`
  - realisierte PnL nur fuer real geschlossene Anteile
  - `exit_reason` aus Exit-Record vor Lifecycle vor markiertem Fallback
- Structure-based Stop-Loss im aktiven Bridge-Pfad eingebaut, mit defensivem Fallback.
- `/execution` und `/organism` enger an denselben Kosten- und Performance-Kern gekoppelt.
- Telegram-Operatorpfad sprachlich und fachlich nachgeschaerft:
  - operative Buy-Signale vs. unvollstaendige Ideen
  - klare Warnlagen fuer Markt, Daten, Kosten und API-Druck
- Erstbetriebs-Readiness gehaertet:
  - leere Runtime-Verzeichnisse
  - erster Execution-/Exit-Lauf ohne Traceback
- Demo-/Seed-Bootstrap fuer lokale Trockenlaeufe angelegt:
  - getrennte Demo-Root
  - klar als `DEMO_ONLY` gekennzeichnet

## 2. Geaenderte Kernmodule

- `modules/virus_bridge/execution_performance.py`
- `modules/virus_bridge/execution_report.py`
- `modules/virus_bridge/exit_flow.py`
- `modules/virus_bridge/execution_workflow.py`
- `modules/virus_bridge/stop_loss.py`
- `modules/virus_bridge/risk_eval.py`
- `modules/virus_bridge/cost_status.py`
- `modules/common/operator_signals.py`
- `modules/common/operator_warnings.py`
- `modules/common/runtime_dirs.py`
- `modules/common/demo_seed.py`
- `modules/organism/monthly_evaluation.py`
- `modules/organism/report_render.py`
- `modules/portfolio_status/status.py`
- `modules/telegram_commands/handlers.py`
- `modules/telegram_commands/poller.py`
- `modules/telegram_commands/ui.py`
- `modules/integration/virus_inbox.py`
- `modules/virus_bridge/intake.py`
- `scripts/bootstrap_demo_desk.py`

## 3. Welche Commands/Reports jetzt operativ besser sind

- `/status`
  - zeigt `API-DRUCK / BETRIEBSSTRESS` jetzt auch ohne Verbose-Modus
- `/portfolio`
  - standardisierte Warnlagen fuer veraltet, gemischt und nur manuelle Daten
- `/execution`
  - trennt offene, teilweise geschlossene und geschlossene Trades sauberer
  - warnt bei fehlenden Quotes fuer offene PnL und nicht gedeckten Kosten
- `/organism`
  - nutzt denselben Kosten-/Execution-Kern wie `/execution`
  - zeigt Warnlagen statt nur weicher Hinweise
- `/tickets`
  - unvollstaendige Buy-Ideen wirken nicht mehr wie operative Tickets
- lokaler Demo-Start
  - `./.venv/bin/python scripts/bootstrap_demo_desk.py --clean`

## 4. Welche Tests gelaufen sind

Heute dokumentiert oder in dieser Session tatsaechlich ausgefuehrt:

- Nachtblock laut `NIGHTLY_HANDOFF.md`: `29 passed`
- Schwellen-/Risk-/Stop-/Trade-Candidate-Suite: `30 passed`
- Operator-/Render-Suite: `9 passed`
- Bridge-/Smoke-Suite: `7 passed`
- Finaler Risk-/Render-Recheck: `30 passed`
- Warn-/Operator-Checks:
  - `tests/test_execution_report.py`
  - `tests/test_portfolio_status.py`
  - `tests/test_telegram_commands_status.py`
  - `tests/test_monthly_evaluation_report.py`
  - `tests/test_ticket_market_open_render.py`
  - `tests/test_trade_ticket_risk_fields.py`
  - Ergebnis: `20 passed`
- Nachbar-Recheck:
  - `tests/test_execution_cost_status.py`
  - `tests/test_incomplete_buy_ticket_delivery.py`
  - `tests/test_buy_message_operational.py`
  - `tests/test_v2_render.py`
  - Ergebnis: `11 passed`
- Demo-Seed-Bootstrap:
  - `tests/test_demo_seed_bootstrap.py`
  - Ergebnis: `2 passed`

Hinweis:
- Die Suites ueberschneiden sich teilweise. Die Zahlen sind deshalb kein deduplizierter Gesamtteststand.

## 5. Was gruen ist

- Der aktive Desk-Pfad laeuft technisch konsistent durch:
  - Proposal
  - TradeCandidate
  - Telegram
  - manueller Entry/Exit
  - Lifecycle
  - `/execution`
  - `/organism`
- Leere und unvollstaendige Erstbetriebszustaende werden defensiv behandelt.
- Warnlagen sind fuer Operator-Pfade vereinheitlicht.
- Ein getrenntes Demo-Bootstrap fuer lokale Trockenlaeufe ist vorhanden und getestet.

## 6. Welche Restrisiken bleiben

- Im echten aktiven Datenpfad liegen weiterhin:
  - `data/virus_bridge/executions`: `0` Dateien
  - `data/virus_bridge/exits`: `0` Dateien
- Damit ist der reale Trade-Pfad code- und testseitig gehaertet, aber noch nicht mit echtem Handelsmaterial bestaetigt.
- Der letzte echte Monatsreport unter [monthly_evaluation_2026_03.json](/opt/portwaechter/data/organism/monthly/monthly_evaluation_2026_03.json) stammt von `2026-03-10T19:22:53+01:00`, steht noch auf `monthly_cost_usd = 29.0` und zeigt weiter `UEBERPRUEFEN`.
- Offene PnL bleibt von belastbaren aktuellen Quotes abhaengig.
- Struktur-Stops greifen nur, wenn im aktiven Datenpfad ein plausibler Strukturanker vorliegt.
- Es gibt keine Broker- oder Depot-API zur automatischen Gegenpruefung echter Executions und Exits.

## 7. Ehrliches Gesamturteil

Technisch:
- Der aktive Pfad ist als kleiner manueller Fund-Desk auf V1-Niveau konsistent und wirkt stabil.

Operativ:
- Der Desk kann heute sinnvoll kontrolliert weiter betrieben werden, aber nur als `Human-in-the-loop`-System.
- Fuer echte Feldsicherheit fehlt noch mindestens ein realer manueller Trade mit sauber erfasstem Entry und Exit.

Wirtschaftlich:
- Wirtschaftlicher Fortschritt ist nicht belegt.
- Aktuell gibt es im echten Datenpfad keine realen Execution-/Exit-Dateien und keinen aktuellen Monatsreport auf der `30 USD`-Referenz.

## 8. Naechste 3 Prioritaeten fuer danach

1. Einen ersten echten manuellen Trade im aktiven Pfad vollstaendig durchlaufen:
   - Kauf
   - Teilverkauf oder Vollverkauf
   - `/execution`
   - `/organism`
2. Danach die echten Reports neu schreiben:
   - frischen Execution-Report
   - frischen Monatsreport mit `30 USD`
3. Erst nach diesem Realbetrieb entscheiden, welche Hardenings aus `/home/ascent/cb-virus-fund` isoliert uebernommen werden sollen.
