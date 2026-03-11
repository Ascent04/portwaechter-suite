# DECISION_REPO_STRATEGY

Stand: 2026-03-11

Pfade:

- Aktiver Produktivpfad: `/opt/portwaechter`
- Separates Referenz-Repo: `/home/ascent/cb-virus-fund`

## 1. Aktueller Ist-Zustand

Der laufende Integrations- und Operator-Pfad liegt im Code heute in `/opt/portwaechter`:

- `modules/v2/main.py`
- `modules/integration/pw_to_virus.py`
- `modules/virus_bridge/main.py`
- `modules/virus_bridge/execution_workflow.py`
- `modules/virus_bridge/exit_flow.py`
- `modules/virus_bridge/execution_report.py`
- `modules/portfolio_status/status.py`
- `modules/organism/monthly_evaluation.py`
- `modules/telegram_commands/poller.py`

Der technische Hauptfluss dort ist:

`PortWaechter V2 -> SignalProposal Queue -> Virus Bridge -> TradeCandidate/Ticket -> Telegram -> manuelle Ausfuehrung -> Lifecycle / Execution / Audit / Monatsbewertung`

Das separate Repo `/home/ascent/cb-virus-fund` hat einen eigenen nativen Laufweg:

- `src/cbv/main.py` scannt intern mit `MomentumScanner`, `BreakoutScanner` und `FundamentalFilter`
- `src/cbv/risk/engine.py` baut aus nativen `SignalProposal`-Objekten `TradeProposal`
- `src/cbv/telegram.py` sendet eigene Telegram-Tickets
- `src/cbv/listener.py` verarbeitet Telegram-Callbacks
- `src/cbv/audit.py` schreibt eine eigene Audit-Kette nach `logs/audit.jsonl`

Es gibt dort keinen file-basierten Intake fuer die `SignalProposal`-Queue aus `/opt/portwaechter/data/integration/signal_proposals/`.

## 2. Staerken des separaten Repos `/home/ascent/cb-virus-fund`

Technisch klar stark im aktuellen Code:

- Gehaertete Audit-Kette mit Hash-Verkettung, Verifikation und Rotation in `src/cbv/audit.py`
- Eigenstaendige Risk Engine mit Drawdown-Regime, Hard Stop, Exposure-Pruefung und Risk-Rejection in `src/cbv/risk/engine.py`
- Typed Core-Modelle `SignalProposal`, `TradeProposal`, `TradeTicket` in `src/cbv/core/__init__.py`
- Config-Fingerprint und Config-Snapshot-Logik in `src/cbv/config.py` und `src/cbv/core/config_snapshot.py`
- Selfcheck- und Heartbeat-Checks in `src/cbv/ops/selfcheck.py` und `src/cbv/ops/heartbeat.py`
- Release Gate in `scripts/gate.sh`
- Evolutions- und Strategy-Multiplier-Logik in `src/cbv/evolution/manager.py`
- Eigene Hardening-Tests fuer Audit, Drawdown, Discipline, Data Quality und Config Snapshot in `tests/test_audit.py`, `tests/test_drawdown_hardening.py`, `tests/test_discipline_hardening.py`, `tests/test_data_quality_gate.py`, `tests/test_config_snapshot_hardening.py`

Das Repo ist damit ein brauchbarer Referenzkern fuer:

- Audit-Haertung
- Config-Haertung
- Selfcheck / Heartbeat
- Drawdown- und Discipline-Gates

## 3. Was im aktiven Pfad `/opt/portwaechter` bereits weiter integriert ist

Im aktiven Pfad sind folgende Bereiche heute weiter oder enger mit dem Realbetrieb verbunden:

- V2-Scanner und Export in die Bridge-Queue in `modules/v2/main.py` und `modules/integration/pw_to_virus.py`
- File-basierte Proposal-Queue mit `data/integration/signal_proposals/` und `data/integration/consumed/`
- Bridge-Intake, TR-Verifikation, Marktstatus, Datenfrische, Stop, Risiko und Groessenlogik in `modules/virus_bridge/main.py`, `modules/virus_bridge/intake.py`, `modules/virus_bridge/risk_eval.py`, `modules/virus_bridge/stop_loss.py`
- Operative Ticket-Reife und Telegram-Textstandard im aktiven Desk-Pfad in `modules/virus_bridge/trade_candidate.py`, `modules/virus_bridge/ticket_render.py`, `modules/common/operator_signals.py`
- Manueller Human-in-the-loop-Workflow fuer Kauf, Teilverkauf, Vollverkauf, Stop-Loss und Ziel erreicht in `modules/virus_bridge/execution_workflow.py` und `modules/virus_bridge/exit_flow.py`
- Ticket-Status, Lifecycle-Dateien und Audit-Referenzen in `modules/virus_bridge/lifecycle.py`, `data/virus_bridge/ticket_state.json`, `data/virus_bridge/ticket_lifecycle/`
- Execution-Wahrheit mit offenen Positionen, Partial Exits, gewichteten Exit-Preisen, Exit-Reason-Rekonstruktion und Kostenstatus in `modules/virus_bridge/execution_performance.py`, `modules/virus_bridge/execution_report.py`, `modules/virus_bridge/cost_status.py`
- Portfolio-Status inklusive PDF-Ingest in `modules/telegram_commands/pdf_upload.py`, `modules/portfolio_status/snapshot.py`, `modules/portfolio_status/status.py`
- Monatsbewertung und Organism-Sicht in `modules/organism/monthly_evaluation.py` und `modules/organism/report_render.py`
- Telegram-Operatorflaeche mit `/status`, `/portfolio`, `/execution`, `/proposals`, `/tickets`, `/organism`, `/help` in `modules/telegram_commands/poller.py`

Das separate Repo hat fuer diese integrierten Bereiche aktuell keine gleichwertige Struktur:

- kein Proposal-Queue-Intake
- keine `ticket_state.json`
- keine `ticket_lifecycle/`
- keine `executions/`- und `exits/`-Dateien
- keine gewichtete Partial-Exit-Auswertung
- keine `/portfolio`, `/execution`, `/proposals`, `/tickets`, `/organism`-Command-Oberflaeche

## 4. Risiken durch parallele Pflege

Parallele Feature-Pflege in beiden Repos erzeugt im aktuellen Stand direkte technische Doppelstrukturen:

- zwei Scannerwelten:
  - `/opt/portwaechter/modules/v2/`
  - `/home/ascent/cb-virus-fund/src/cbv/research/`
- zwei Risk-Kerne:
  - `/opt/portwaechter/modules/virus_bridge/risk_eval.py`
  - `/home/ascent/cb-virus-fund/src/cbv/risk/engine.py`
- zwei Telegram-Bedienpfade:
  - `/opt/portwaechter/modules/telegram_commands/poller.py`
  - `/home/ascent/cb-virus-fund/src/cbv/telegram.py` plus `src/cbv/listener.py`
- zwei Universe-/TR-Verifikationsquellen:
  - `/opt/portwaechter/config/universe_tr_verified.json`
  - `/home/ascent/cb-virus-fund/configs/universe.json`
- zwei Performance- und Audit-Wahrheiten:
  - `/opt/portwaechter/data/virus_bridge/*` plus `/opt/portwaechter/data/audit/portfolio_audit.jsonl`
  - `/home/ascent/cb-virus-fund/logs/audit.jsonl`

Die Folgen waeren im Betrieb:

- dieselben Trades koennten in zwei verschiedenen Wahrheitsmodellen landen
- Ticket-, Exit- und Monatszahlen wuerden auseinanderlaufen
- dieselbe Telegram-Gruppe koennte aus zwei Bots oder zwei Logiken bedient werden
- Thresholds, Universe und Risk-Regeln muessten doppelt synchron gehalten werden

## 5. Merge-Bewertung

Ein Merge ist im aktuellen Stand technisch nicht sinnvoll.

Gruende aus dem Code:

- `src/cbv/main.py` erwartet interne Scanner-Signale und keinen externen Queue-Intake aus PortWaechter V2
- `src/cbv/listener.py` bietet nur Callback-Handling und `/status`, nicht die aktive Operator-Flaeche aus `/opt/portwaechter/modules/telegram_commands/poller.py`
- `src/cbv/operations/bookkeeper.py` kennt `TRADE_CLOSED` und `MANUAL_PNL_UPDATE`, aber keine file-basierte Partial-Exit- und Restmengenlogik
- `src/cbv/operations/stats.py` rekonstruiert Performance aus `logs/audit.jsonl`, waehrend `/opt/portwaechter` bereits `executions/`, `exits/`, `ticket_state.json` und `ticket_lifecycle/` als operative Source of Truth nutzt
- `src/cbv/core/__init__.py` arbeitet mit einem schmalen nativen `SignalProposal`-Modell, waehrend `/opt/portwaechter` bereits breitere Bridge-Proposals mit Marktstatus, Datenfrische, Groessen, operativer Ticket-Reife und Lifecycle-Metadaten verarbeitet

Ein Merge jetzt wuerde daher nicht nur Code verschieben. Er wuerde die aktive Betriebswahrheit ummodellieren.

Das waere im aktuellen Stand schaedlich, weil:

- der laufende Desk-Pfad in `/opt/portwaechter` bereits durchgaengig integriert ist
- die Source of Truth fuer manuelle Trades, Partial Exits und Monatsbewertung dort bereits existiert
- das separate Repo diese Betriebsdaten heute nicht nativ fuehrt

## 6. Empfehlung

Technische Empfehlung fuer den aktuellen Stand:

- Aktiv weiterfuehren in `/opt/portwaechter`
- `/home/ascent/cb-virus-fund` als Referenz-Repo und spaeteren Hardened-Kern behalten
- Kein paralleler Feature-Ausbau fuer den operativen Desk in `/home/ascent/cb-virus-fund`

Was im separaten Repo vorerst nicht parallel gepflegt werden sollte:

- kein zweiter aktiver Scannerpfad
- keine zweite aktive Telegram-Oberflaeche fuer denselben Desk
- keine zweite PnL- oder Monatswahrheit
- keine zweite operative Universe-/TR-Verifikationsquelle
- keine zweite manuelle Execution-/Exit-Erfassung

## 7. Konkrete Naechstschritte

1. `/opt/portwaechter` als einzigen aktiven Betriebs- und Integrationspfad weiterfuehren.
2. `/home/ascent/cb-virus-fund` nur noch als Referenz fuer isolierte Uebernahmen verwenden.
3. Falls Uebernahmen noetig sind, nur kleine abgegrenzte Bausteine portieren:
   - Audit-Kettenlogik aus `src/cbv/audit.py`
   - Config-Snapshot-/Fingerprint-Logik aus `src/cbv/config.py` und `src/cbv/core/config_snapshot.py`
   - Selfcheck-/Heartbeat-Muster aus `src/cbv/ops/selfcheck.py` und `src/cbv/ops/heartbeat.py`
   - einzelne Hardening-Tests als Vorlage
4. Keine Portierung ganzer Hauptpfade wie `src/cbv/main.py`, `src/cbv/telegram.py` oder `src/cbv/listener.py` in den laufenden Desk ohne gesonderten Architekturentscheid.

## 8. Was erst nach echtem Realbetrieb entschieden werden sollte

Erst nach echtem Realbetrieb im aktiven Pfad sollten diese Punkte neu bewertet werden:

- ob die Audit-Kette in `/opt/portwaechter` auf das Hash-Chain-Modell aus `src/cbv/audit.py` umgestellt werden soll
- ob ein eigener Selfcheck-/Heartbeat-Layer aus dem separaten Repo im aktiven Desk echten Mehrwert bringt
- ob Config-Fingerprint und Config-Snapshot pro Ticket fuer den laufenden Desk noetig sind
- ob spaeter einzelne Risk-Haertungen aus `src/cbv/risk/engine.py` in den Bridge-Pfad uebernommen werden sollen

Diese Entscheidung sollte erst fallen, wenn im aktiven Pfad reale Betriebsdaten vorliegen aus:

- `data/virus_bridge/executions/`
- `data/virus_bridge/exits/`
- `data/virus_bridge/ticket_lifecycle/`
- `data/organism/monthly/monthly_evaluation_*.json`

Bis dahin ist die klare technische Linie:

- `/opt/portwaechter` bleibt aktiv
- `/home/ascent/cb-virus-fund` bleibt Referenz
- kein Merge des Hauptpfads im aktuellen Stand
